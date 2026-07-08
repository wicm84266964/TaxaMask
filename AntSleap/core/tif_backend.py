import json
import os
import signal
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .safe_io import atomic_write_json
from .tif_prediction_policy import can_import_prediction_target, validate_prediction_volume
from .tif_project import TifProjectManager
from .tif_export import export_tif_part_training_dataset, export_tif_training_dataset
from .tif_volume_io import copy_volume_sidecar, read_volume_metadata, volume_sidecar_exists
from .tif_write_guard import WriteIntent, ensure_write_allowed


TIF_BACKEND_CONTRACT_SCHEMA_VERSION = "ant3d_tif_backend_contract_v1"
TIF_BACKEND_RESULT_SCHEMA_VERSION = "ant3d_tif_backend_result_v1"
TIF_MODEL_MANIFEST_SCHEMA_VERSION = "ant3d_tif_model_manifest_v1"
TIF_NNUNET_V2_BACKEND_ID = "taxamask_tif_nnunet_v2_backend"
TIF_NNUNET_V2_ADAPTER_MODULE = "AntSleap.tools.tif_nnunet_v2_backend"
TIF_NNUNET_V2_REQUIRED_COMMANDS = (
    "nnUNetv2_plan_and_preprocess",
    "nnUNetv2_train",
    "nnUNetv2_predict",
)


DEFAULT_TIF_BACKEND_CONFIG = {
    "backend_id": "custom_tif_backend",
    "display_name": "TIF Volume Backend",
    "python_executable": "python",
    "prepare_dataset_command": "",
    "train_command": "",
    "predict_command": "",
    "model_manifest": "",
    "export_formats": "ome_tiff,nrrd,mha,nifti",
}


def nnunet_v2_tif_backend_preset(python_executable="python"):
    command = "{python} -m AntSleap.tools.tif_nnunet_v2_backend --contract {contract_json}"
    return {
        "backend_id": TIF_NNUNET_V2_BACKEND_ID,
        "display_name": "nnU-Net v2 TIF Region Segmentation",
        "python_executable": str(python_executable or "python"),
        "prepare_dataset_command": command,
        "train_command": command,
        "predict_command": command,
        "model_manifest": "",
        "export_formats": "ome_tiff,nrrd,mha,nifti",
    }


def _strip_shell_quotes(value):
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _is_generic_python_command(value):
    text = _strip_shell_quotes(value).lower()
    return text in {"python", "python.exe", "py", "py.exe", "python3", "python3.exe"}


def _resolve_python_path(value, env=None):
    text = _strip_shell_quotes(value)
    if not text:
        return ""
    path = Path(text)
    if path.is_dir():
        candidates = [path / "python.exe", path / "Scripts" / "python.exe"] if os.name == "nt" else [path / "bin" / "python", path / "python"]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return ""
    if path.exists():
        return str(path.resolve())
    if _is_generic_python_command(text) or (not path.is_absolute() and os.path.basename(text) == text):
        active_env = env if isinstance(env, dict) else os.environ
        resolved = shutil.which(text, path=active_env.get("PATH"))
        return str(Path(resolved).resolve()) if resolved else ""
    return ""


def _script_dirs_for_python(python_executable):
    resolved = _resolve_python_path(python_executable) or _strip_shell_quotes(python_executable)
    if not resolved:
        return []
    python_path = Path(resolved)
    parent = python_path.parent
    candidates = []
    if os.name == "nt":
        candidates.extend([parent, parent / "Scripts", parent.parent / "Scripts"])
    else:
        candidates.extend([parent, parent / "bin", parent.parent / "bin"])
    unique = []
    seen = set()
    for item in candidates:
        text = str(item)
        key = os.path.normcase(os.path.abspath(text))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _python_has_nnunet_v2_commands(python_executable, env=None):
    resolved = _resolve_python_path(python_executable, env=env)
    if not resolved:
        return False
    suffixes = (".exe", ".bat", ".cmd", "") if os.name == "nt" else ("",)
    for command in TIF_NNUNET_V2_REQUIRED_COMMANDS:
        found = False
        for scripts_dir in _script_dirs_for_python(resolved):
            for suffix in suffixes:
                if (scripts_dir / f"{command}{suffix}").exists():
                    found = True
                    break
            if found:
                break
        if not found:
            return False
    return True


def _iter_conda_env_roots(env=None, extra_roots=None):
    active_env = env if isinstance(env, dict) else os.environ
    roots = []

    def add(path):
        if not path:
            return
        try:
            root = Path(path).expanduser()
        except TypeError:
            return
        key = os.path.normcase(os.path.abspath(str(root)))
        if key not in {item[0] for item in roots}:
            roots.append((key, root))

    for path in extra_roots or []:
        add(path)
    for key in ("CONDA_PREFIX", "MAMBA_ROOT_PREFIX", "CONDA_ROOT"):
        prefix = active_env.get(key)
        if prefix:
            prefix_path = Path(prefix)
            add(prefix_path)
            add(prefix_path / "envs")
            if prefix_path.parent.name.lower() == "envs":
                add(prefix_path.parent)
                add(prefix_path.parent.parent / "envs")
    add(Path(sys.prefix))
    sys_prefix = Path(sys.prefix)
    if sys_prefix.parent.name.lower() == "envs":
        add(sys_prefix.parent)
    home = Path.home()
    for root_name in ("anaconda3", "miniconda3", "miniforge3", "mambaforge"):
        add(home / root_name / "envs")
    for item in str(active_env.get("PATH") or "").split(os.pathsep):
        if not item:
            continue
        item_path = Path(item)
        if item_path.name.lower() in {"scripts", "bin"}:
            prefix = item_path.parent
            add(prefix)
            if prefix.parent.name.lower() == "envs":
                add(prefix.parent)
    return [item[1] for item in roots]


def _candidate_python_in_prefix(prefix):
    prefix = Path(prefix)
    candidates = [prefix / "python.exe", prefix / "Scripts" / "python.exe"] if os.name == "nt" else [prefix / "bin" / "python", prefix / "python"]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def _iter_nnunet_python_candidates(preferred_python="", env=None, extra_roots=None):
    active_env = env if isinstance(env, dict) else os.environ
    seen = set()

    def emit(path):
        resolved = _resolve_python_path(path, env=active_env)
        if not resolved:
            return
        key = os.path.normcase(os.path.abspath(resolved))
        if key in seen:
            return
        seen.add(key)
        yield resolved

    for path in (preferred_python, active_env.get("TAXAMASK_TIF_NNUNET_PYTHON"), active_env.get("TAXAMASK_TIF_BACKEND_PYTHON"), sys.executable):
        yield from emit(path)
    for root in _iter_conda_env_roots(env=active_env, extra_roots=extra_roots):
        if not root.exists():
            continue
        direct = _candidate_python_in_prefix(root)
        if direct:
            yield from emit(direct)
        if root.name.lower() == "envs" or not direct:
            try:
                children = list(root.iterdir())
            except OSError:
                children = []
            for child in children:
                if child.is_dir():
                    candidate = _candidate_python_in_prefix(child)
                    if candidate:
                        yield from emit(candidate)


def resolve_nnunet_v2_backend_python(preferred_python="python", env=None, extra_roots=None):
    for candidate in _iter_nnunet_python_candidates(preferred_python, env=env, extra_roots=extra_roots):
        if _python_has_nnunet_v2_commands(candidate, env=env):
            return candidate
    return ""


def _command_uses_nnunet_v2_adapter(command):
    return TIF_NNUNET_V2_ADAPTER_MODULE in str(command or "")


def normalize_tif_backend_runtime_config(config, action="", command_template="", env=None, extra_roots=None):
    clean = sanitize_tif_backend_config(config)
    if clean.get("backend_id") != TIF_NNUNET_V2_BACKEND_ID:
        return clean
    action_key = {
        "prepare_dataset": "prepare_dataset_command",
        "train": "train_command",
        "predict": "predict_command",
    }.get(str(action or ""), "")
    commands = []
    if command_template:
        commands = [command_template]
    elif action_key:
        commands = [clean.get(action_key, "")]
    else:
        commands = [clean.get(key, "") for key in ("prepare_dataset_command", "train_command", "predict_command")]
    if not any(_command_uses_nnunet_v2_adapter(command) for command in commands):
        return clean
    current_python = clean.get("python_executable") or "python"
    if _python_has_nnunet_v2_commands(current_python, env=env):
        resolved = _resolve_python_path(current_python, env=env)
        if resolved and _is_generic_python_command(current_python):
            clean["python_executable"] = resolved
        return clean
    resolved = resolve_nnunet_v2_backend_python(current_python, env=env, extra_roots=extra_roots)
    if resolved:
        clean["python_executable"] = resolved
    return clean


def _now_stamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(value):
    text = str(value or "").strip()
    clean = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text)
    return clean.strip("_") or "tif_backend"


def sanitize_tif_backend_config(config):
    clean = dict(DEFAULT_TIF_BACKEND_CONFIG)
    if isinstance(config, dict):
        for key in clean.keys():
            value = config.get(key)
            if value is not None:
                clean[key] = str(value)
    clean["backend_id"] = _safe_id(clean.get("backend_id") or "custom_tif_backend")
    clean["display_name"] = clean.get("display_name") or clean["backend_id"]
    clean["python_executable"] = clean.get("python_executable") or "python"
    return clean


def _write_json(path, payload):
    atomic_write_json(path, payload, indent=2, ensure_ascii=False)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _emit_progress(progress_callback, current, total, message):
    if not progress_callback:
        return
    progress_callback(int(current), int(total), str(message or ""))


def _cancel_requested(cancel_check):
    if not cancel_check:
        return False
    try:
        return bool(cancel_check())
    except Exception:
        return False


def _require_guard(result, prefix):
    if result:
        return result
    reason = getattr(result, "reason", "denied")
    details = getattr(result, "details", {})
    raise ValueError(f"{prefix}:{reason}:{details}")


def _tail_lines(path, max_lines=8):
    if not path or not os.path.exists(path):
        return []
    max_lines = max(1, int(max_lines or 1))
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            block_size = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= max_lines:
                read_size = min(block_size, size)
                size -= read_size
                handle.seek(size)
                data = handle.read(read_size) + data
        lines = data.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return lines[-max_lines:]


def _terminate_process_tree(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:
            process.terminate()


def _kill_process(process):
    if process is None or process.poll() is not None:
        return
    if os.name == "nt":
        process.kill()
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            process.kill()


def _source_repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


class TifBackendRunner:
    def __init__(self, project_manager, backend_config=None, runs_root=None):
        if not isinstance(project_manager, TifProjectManager):
            raise TypeError("project_manager_must_be_tif_project_manager")
        self.project_manager = project_manager
        self.backend_config = normalize_tif_backend_runtime_config(backend_config or {})
        project_dir = self.project_manager.project_dir
        self.runs_root = os.path.abspath(runs_root or os.path.join(project_dir, "runs"))
        self.last_run_id = ""
        self.last_run_dir = ""
        self.last_result_json = ""

    def create_run_dir(self, action):
        backend_id = _safe_id(self.backend_config.get("backend_id"))
        run_id = f"{_safe_id(action)}_{_now_stamp()}_{backend_id}"
        run_dir = os.path.join(self.runs_root, _safe_id(action), run_id)
        os.makedirs(os.path.join(run_dir, "outputs"), exist_ok=True)
        os.makedirs(os.path.join(run_dir, "logs"), exist_ok=True)
        return run_id, run_dir

    def build_contract(self, action, specimen_ids=None, run_id=None, run_dir=None, dataset_dir="", model_manifest="", result_json="", part_refs=None, input_scope="auto"):
        action = str(action or "").strip()
        if action not in {"prepare_dataset", "train", "predict"}:
            raise ValueError(f"unsupported_tif_backend_action:{action}")
        if run_id is None or run_dir is None:
            run_id, run_dir = self.create_run_dir(action)
        output_dir = os.path.join(run_dir, "outputs")
        result_json = result_json or os.path.join(run_dir, "result.json")
        model_manifest = model_manifest or self.backend_config.get("model_manifest", "")
        if model_manifest:
            model_manifest = self._format_template(model_manifest, run_dir, "")

        scope = str(input_scope or "auto").strip().lower()
        if scope not in {"auto", "part_reslice", "top_level_volume"}:
            raise ValueError(f"unsupported_tif_backend_input_scope:{input_scope}")
        selected_parts = []
        selected_specimens = []
        if scope in {"auto", "part_reslice"}:
            selected_parts = self._select_part_samples(action, specimen_ids=specimen_ids, part_refs=part_refs)
            if selected_parts:
                selected_specimens = self._contract_specimens_from_part_samples(selected_parts)
                scope = "part_reslice"
            elif scope == "part_reslice" or part_refs is not None:
                raise ValueError(f"no_tif_part_samples:{action}")
        if scope in {"auto", "top_level_volume"} and not selected_parts:
            selected_specimens = self._select_specimens(action, specimen_ids)
            if not selected_specimens:
                raise ValueError(f"no_tif_specimen_samples:{action}")
            scope = "top_level_volume"
        return {
            "schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
            "action": action,
            "backend_id": self.backend_config.get("backend_id"),
            "input_scope": scope,
            "project_json": os.path.abspath(self.project_manager.current_project_path or ""),
            "run_id": run_id,
            "run_dir": os.path.abspath(run_dir),
            "dataset_dir": os.path.abspath(dataset_dir) if dataset_dir else os.path.join(run_dir, "dataset"),
            "model_manifest": os.path.abspath(model_manifest) if model_manifest else "",
            "output_dir": os.path.abspath(output_dir),
            "result_json": os.path.abspath(result_json),
            "specimens": selected_specimens,
            "part_samples": selected_parts,
            "training_config": {
                "model_family": self.backend_config.get("backend_id"),
                "normalization": "backend_default",
                "augmentation": "backend_default",
            },
            "safety": {
                "protect_manual_truth": True,
                "allow_editable_ai_result_as_training_label": False,
                "allow_model_draft_as_training_label": False,
                "allow_overwrite_outputs": False,
            },
        }

    def write_contract(self, contract):
        path = os.path.join(contract["run_dir"], "contract.json")
        _write_json(path, contract)
        return path

    def run_action(self, action, specimen_ids=None, dataset_dir="", model_manifest="", part_refs=None, input_scope="auto", progress_callback=None, cancel_check=None):
        self.backend_config = normalize_tif_backend_runtime_config(self.backend_config, action=action)
        run_id, run_dir = self.create_run_dir(action)
        self.last_run_id = run_id
        self.last_run_dir = os.path.abspath(run_dir)
        self.last_result_json = os.path.abspath(os.path.join(run_dir, "result.json"))
        _emit_progress(progress_callback, 0, 100, f"Creating {action} run...\nRun folder: {self.last_run_dir}")
        if _cancel_requested(cancel_check):
            raise RuntimeError(f"tif_backend_{action}_cancelled")
        contract = self.build_contract(action, specimen_ids, run_id, run_dir, dataset_dir, model_manifest, part_refs=part_refs, input_scope=input_scope)
        self.last_result_json = os.path.abspath(contract.get("result_json") or self.last_result_json)
        sample_count = len(contract.get("part_samples", []) or []) if contract.get("input_scope") == "part_reslice" else len(contract.get("specimens", []) or [])
        sample_label = "part sample" if contract.get("input_scope") == "part_reslice" else "top-level volume"
        _emit_progress(progress_callback, 5, 100, f"Built {action} contract for {sample_count} {sample_label}(s).\nResult JSON: {self.last_result_json}")
        if _cancel_requested(cancel_check):
            raise RuntimeError(f"tif_backend_{action}_cancelled")
        if action == "prepare_dataset":
            export_formats = [
                item.strip()
                for item in str(self.backend_config.get("export_formats", "")).split(",")
                if item.strip()
            ]
            if contract.get("input_scope") == "part_reslice":
                _emit_progress(progress_callback, 10, 100, "Exporting part-reslice training dataset...")
                export_result = export_tif_part_training_dataset(
                    self.project_manager,
                    contract["dataset_dir"],
                    part_refs=[
                        {
                            "specimen_id": item["specimen_id"],
                            "part_id": item["part_id"],
                            "reslice_id": item["reslice_id"],
                        }
                        for item in contract.get("part_samples", [])
                    ],
                    formats=export_formats or None,
                    require_train_ready=True,
                )
            else:
                _emit_progress(progress_callback, 10, 100, "Exporting top-level volume training dataset...")
                export_result = export_tif_training_dataset(
                    self.project_manager,
                    contract["dataset_dir"],
                    specimen_ids=[item.get("specimen_id", "") for item in contract.get("specimens", [])],
                    formats=export_formats or None,
                    require_train_ready=True,
                )
            contract["dataset_manifest"] = export_result["manifest_path"]
            contract["dataset_formats"] = export_result["manifest"].get("formats", [])
            _emit_progress(progress_callback, 35, 100, f"Prepared dataset manifest: {export_result['manifest_path']}")
        if _cancel_requested(cancel_check):
            raise RuntimeError(f"tif_backend_{action}_cancelled")
        contract_path = self.write_contract(contract)
        _emit_progress(progress_callback, 40, 100, f"Wrote backend contract: {contract_path}")
        command_key = {
            "prepare_dataset": "prepare_dataset_command",
            "train": "train_command",
            "predict": "predict_command",
        }[action]
        command = self.backend_config.get(command_key, "").strip()
        if not command:
            raise ValueError(f"tif_backend_{action}_command_missing")
        self._run_command(command, contract_path, run_dir, action, progress_callback=progress_callback, cancel_check=cancel_check)
        _emit_progress(progress_callback, 82, 100, f"Reading {action} result...")
        result = self.read_result(contract["result_json"])
        if action == "predict":
            _emit_progress(progress_callback, 90, 100, "Importing predictions as editable AI results...")
            imported = self.import_prediction_result(result)
        else:
            imported = []
        _emit_progress(progress_callback, 96, 100, f"Registering {action} run...")
        self._register_run(contract, result)
        _emit_progress(progress_callback, 100, 100, f"Finished {action} run: {run_dir}")
        return {
            "run_id": run_id,
            "run_dir": run_dir,
            "contract_json": contract_path,
            "contract": contract,
            "result": result,
            "imported": imported,
        }

    def read_result(self, result_json):
        result = _read_json(result_json)
        result["_result_json"] = os.path.abspath(result_json)
        if result.get("schema_version") != TIF_BACKEND_RESULT_SCHEMA_VERSION:
            raise ValueError(f"invalid_tif_backend_result_schema:{result.get('schema_version')}")
        if result.get("contract_schema_version") != TIF_BACKEND_CONTRACT_SCHEMA_VERSION:
            raise ValueError(f"invalid_tif_backend_contract_schema:{result.get('contract_schema_version')}")
        if result.get("status") not in {"success", "partial_success"}:
            raise ValueError(f"tif_backend_result_not_success:{result.get('status')}")
        return result

    def import_prediction_result(self, result):
        imported = []
        for artifact in result.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            role = artifact.get("role")
            if artifact.get("type") != "prediction_label_volume" or role not in {"model_draft", "editable_ai_result"}:
                continue
            specimen_id = str(artifact.get("specimen_id", "")).strip()
            part_id = str(artifact.get("part_id", "")).strip()
            source_path = self._artifact_abs_path(result, artifact.get("path", ""))
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                raise ValueError(f"prediction_unknown_specimen:{specimen_id}")
            if not volume_sidecar_exists(source_path):
                raise FileNotFoundError(source_path)
            source_meta = read_volume_metadata(source_path)
            audit_metadata = {
                "prediction_id": artifact.get("prediction_id") or result.get("run_id") or "",
                "source_model": result.get("provenance", {}).get("model_manifest", ""),
                "run_id": result.get("run_id", ""),
                "result_json": result.get("_result_json", ""),
            }
            if part_id:
                part = self.project_manager.get_part(specimen_id, part_id, default=None)
                if part is None:
                    raise ValueError(f"prediction_unknown_part:{specimen_id}:{part_id}")
                reslice_id = str(artifact.get("reslice_id") or "").strip()
                expected_shape = self.project_manager.evaluate_part_predict_ready(specimen_id, part_id, reslice_id).get("input_shape_zyx", [])
                validation = validate_prediction_volume(
                    prediction_shape_zyx=source_meta.get("shape_zyx", []),
                    expected_shape_zyx=expected_shape,
                    dtype=source_meta.get("dtype", ""),
                    context={
                        "specimen_id": specimen_id,
                        "part_id": part_id,
                        "reslice_id": reslice_id,
                        "run_id": result.get("run_id", ""),
                    },
                )
                if not validation and validation.reason == "prediction_shape_mismatch":
                    raise ValueError(f"prediction_shape_mismatch:{specimen_id}:{part_id}:{source_meta.get('shape_zyx')}:{expected_shape}")
                _require_guard(validation, "tif_prediction_policy_denied")
                prediction_id = artifact.get("prediction_id") or f"{result.get('run_id')}_{specimen_id}_{part_id}"
                audit_metadata["prediction_id"] = prediction_id
                if reslice_id:
                    label_root = os.path.join(
                        self.project_manager.part_dir(specimen_id, part_id),
                        "reslices",
                        reslice_id,
                        "labels",
                    )
                else:
                    label_root = os.path.join(self.project_manager.part_dir(specimen_id, part_id), "labels")
                backup_rel = os.path.join(label_root, "raw_ai_prediction_backup.ome.zarr").replace("\\", "/")
                editable_rel = os.path.join(label_root, "editable_ai_result.ome.zarr").replace("\\", "/")
                backup_abs = self.project_manager.to_absolute(backup_rel)
                editable_abs = self.project_manager.to_absolute(editable_rel)
                for target_abs, target_role in (
                    (backup_abs, "raw_ai_prediction_backup"),
                    (editable_abs, "editable_ai_result"),
                ):
                    _require_guard(
                        can_import_prediction_target(
                            target_role,
                            source_role="backend_prediction_result",
                            overwrite_existing=True,
                            audit_metadata=audit_metadata,
                        ),
                        "tif_prediction_policy_denied",
                    )
                    ensure_write_allowed(
                        WriteIntent(
                            target_path=target_abs,
                            project_root=self.project_manager.project_dir,
                            source_path=source_path,
                            source_role="backend_prediction_result",
                            target_role=target_role,
                            operation="backend_prediction_import",
                            audit_metadata=audit_metadata,
                            allow_overwrite=True,
                            allowed_roots=(self.project_manager.project_dir,),
                        )
                    )
                copy_volume_sidecar(source_path, backup_abs, role="raw_ai_prediction_backup")
                copy_volume_sidecar(source_path, editable_abs, role="editable_ai_result")
                register = self.project_manager.register_part_reslice_label_volume if reslice_id else self.project_manager.register_part_label_volume
                if reslice_id:
                    backup = register(
                        specimen_id,
                        part_id,
                        reslice_id,
                        "raw_ai_prediction_backup",
                        backup_rel,
                        source_meta["shape_zyx"],
                        source_meta["dtype"],
                        status="raw_backup",
                        prediction_id=prediction_id,
                        source_model=result.get("provenance", {}).get("model_manifest", ""),
                        spacing_zyx=source_meta.get("spacing_zyx"),
                        spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                        orientation=source_meta.get("orientation", "local_axis_reslice"),
                        operation="prediction_raw_backup_import",
                        audit_metadata=audit_metadata,
                        save=False,
                    )
                    editable = register(
                        specimen_id,
                        part_id,
                        reslice_id,
                        "editable_ai_result",
                        editable_rel,
                        source_meta["shape_zyx"],
                        source_meta["dtype"],
                        status="pending_review",
                        prediction_id=prediction_id,
                        source_model=result.get("provenance", {}).get("model_manifest", ""),
                        spacing_zyx=source_meta.get("spacing_zyx"),
                        spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                        orientation=source_meta.get("orientation", "local_axis_reslice"),
                        operation="prediction_review_import",
                        audit_metadata=audit_metadata,
                        save=False,
                    )
                else:
                    backup = register(
                        specimen_id,
                        part_id,
                        "raw_ai_prediction_backup",
                        backup_rel,
                        source_meta["shape_zyx"],
                        source_meta["dtype"],
                        status="raw_backup",
                        prediction_id=prediction_id,
                        source_model=result.get("provenance", {}).get("model_manifest", ""),
                        spacing_zyx=source_meta.get("spacing_zyx"),
                        spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                        orientation=source_meta.get("orientation", "unknown"),
                        operation="prediction_raw_backup_import",
                        audit_metadata=audit_metadata,
                        save=False,
                    )
                    editable = register(
                        specimen_id,
                        part_id,
                        "editable_ai_result",
                        editable_rel,
                        source_meta["shape_zyx"],
                        source_meta["dtype"],
                        status="pending_review",
                        prediction_id=prediction_id,
                        source_model=result.get("provenance", {}).get("model_manifest", ""),
                        spacing_zyx=source_meta.get("spacing_zyx"),
                        spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                        orientation=source_meta.get("orientation", "unknown"),
                        operation="prediction_review_import",
                        audit_metadata=audit_metadata,
                        save=False,
                    )
                imported.append({"editable_ai_result": editable, "raw_ai_prediction_backup": backup})
                continue

            working_shape = (specimen.get("working_volume") or {}).get("shape_zyx", [])
            validation = validate_prediction_volume(
                prediction_shape_zyx=source_meta.get("shape_zyx", []),
                expected_shape_zyx=working_shape,
                dtype=source_meta.get("dtype", ""),
                context={
                    "specimen_id": specimen_id,
                    "part_id": "",
                    "reslice_id": "",
                    "run_id": result.get("run_id", ""),
                },
            )
            if not validation and validation.reason == "prediction_shape_mismatch":
                raise ValueError(f"prediction_shape_mismatch:{specimen_id}:{source_meta.get('shape_zyx')}:{working_shape}")
            _require_guard(validation, "tif_prediction_policy_denied")

            prediction_id = artifact.get("prediction_id") or f"{result.get('run_id')}_{specimen_id}"
            audit_metadata["prediction_id"] = prediction_id
            backup_rel = os.path.join(
                self.project_manager.specimen_dir(specimen_id),
                "labels",
                "raw_ai_prediction_backup.ome.zarr",
            ).replace("\\", "/")
            editable_rel = os.path.join(
                self.project_manager.specimen_dir(specimen_id),
                "labels",
                "working_edit.ome.zarr",
            ).replace("\\", "/")
            draft_rel = os.path.join(
                self.project_manager.specimen_dir(specimen_id),
                "labels",
                "model_draft",
                f"{_safe_id(prediction_id)}.ome.zarr",
            ).replace("\\", "/")
            backup_abs = self.project_manager.to_absolute(backup_rel)
            editable_abs = self.project_manager.to_absolute(editable_rel)
            draft_abs = self.project_manager.to_absolute(draft_rel)
            if os.path.exists(draft_abs):
                raise FileExistsError(draft_abs)
            for target_abs, target_role, allow_overwrite in (
                (backup_abs, "raw_ai_prediction_backup", True),
                (editable_abs, "working_edit", True),
                (draft_abs, "model_draft", False),
            ):
                _require_guard(
                    can_import_prediction_target(
                        target_role,
                        source_role="backend_prediction_result",
                        overwrite_existing=allow_overwrite,
                        audit_metadata=audit_metadata,
                    ),
                    "tif_prediction_policy_denied",
                )
                ensure_write_allowed(
                    WriteIntent(
                        target_path=target_abs,
                        project_root=self.project_manager.project_dir,
                        source_path=source_path,
                        source_role="backend_prediction_result",
                        target_role=target_role,
                        operation="backend_prediction_import",
                        audit_metadata=audit_metadata,
                        allow_overwrite=allow_overwrite,
                        allowed_roots=(self.project_manager.project_dir,),
                    )
                )
            backup_meta = copy_volume_sidecar(source_path, backup_abs, role="raw_ai_prediction_backup")
            editable_meta = copy_volume_sidecar(source_path, editable_abs, role="working_edit")
            copy_volume_sidecar(source_path, draft_abs, role="model_draft")
            labels = specimen.setdefault("labels", {})
            labels["raw_ai_prediction_backup"] = self.project_manager._volume_payload(
                backup_rel,
                backup_meta["shape_zyx"],
                backup_meta["dtype"],
                backup_meta.get("spacing_zyx"),
                backup_meta.get("spacing_unit", "micrometer"),
                backup_meta.get("orientation", "unknown"),
                backup_meta.get("format", ""),
            )
            labels["raw_ai_prediction_backup"]["role"] = "raw_ai_prediction_backup"
            labels["raw_ai_prediction_backup"]["status"] = "raw_backup"
            labels["raw_ai_prediction_backup"]["prediction_id"] = prediction_id
            editable = self.project_manager.register_label_volume(
                specimen_id,
                "working_edit",
                editable_rel,
                editable_meta["shape_zyx"],
                editable_meta["dtype"],
                status="pending_review",
                spacing_zyx=editable_meta.get("spacing_zyx"),
                spacing_unit=editable_meta.get("spacing_unit", "micrometer"),
                orientation=editable_meta.get("orientation", "unknown"),
                fmt=editable_meta.get("format", ""),
                operation="prediction_review_import",
                audit_metadata=audit_metadata,
                save=False,
            )
            draft = self.project_manager.add_model_draft(
                specimen_id,
                draft_rel,
                source_meta["shape_zyx"],
                source_meta["dtype"],
                prediction_id=prediction_id,
                source_model=result.get("provenance", {}).get("model_manifest", ""),
                spacing_zyx=source_meta.get("spacing_zyx"),
                spacing_unit=source_meta.get("spacing_unit", "micrometer"),
                orientation=source_meta.get("orientation", "unknown"),
                save=False,
            )
            specimen["review_status"] = "pending_review"
            specimen["train_ready"] = False
            imported.append({"working_edit": editable, "raw_ai_prediction_backup": labels["raw_ai_prediction_backup"], "model_draft": draft})
        self.project_manager.save_project()
        return imported

    def _contract_specimens_from_part_samples(self, part_samples):
        by_id = {}
        for sample in part_samples:
            specimen_id = str(sample.get("specimen_id") or "")
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                continue
            item = by_id.setdefault(
                specimen_id,
                {
                    "specimen_id": specimen_id,
                    "display_name": specimen.get("display_name", specimen_id),
                    "modality": specimen.get("modality", "unknown"),
                    "part_ids": [],
                },
            )
            part_id = str(sample.get("part_id") or "")
            if part_id and part_id not in item["part_ids"]:
                item["part_ids"].append(part_id)
        return list(by_id.values())

    def _select_part_samples(self, action, specimen_ids=None, part_refs=None):
        refs = []
        if part_refs is not None:
            refs = [
                {
                    "specimen_id": str(item.get("specimen_id") or ""),
                    "part_id": str(item.get("part_id") or ""),
                    "reslice_id": str(item.get("reslice_id") or ""),
                }
                for item in part_refs
                if isinstance(item, dict)
            ]
        else:
            wanted = {str(item) for item in specimen_ids} if specimen_ids else None
            for item in self.project_manager.list_train_ready_parts(specimen_ids=wanted):
                refs.append(
                    {
                        "specimen_id": item["readiness"]["specimen_id"],
                        "part_id": item["readiness"]["part_id"],
                        "reslice_id": item["readiness"].get("reslice_id", ""),
                    }
                )
        samples = []
        for ref in refs:
            specimen_id = ref["specimen_id"]
            part_id = ref["part_id"]
            if not specimen_id or not part_id:
                continue
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            part = self.project_manager.get_part(specimen_id, part_id, default=None)
            if specimen is None or part is None:
                raise KeyError(f"unknown_part_ref:{specimen_id}:{part_id}")
            readiness = (
                self.project_manager.evaluate_part_predict_ready(specimen_id, part_id, ref.get("reslice_id", ""))
                if action == "predict"
                else self.project_manager.evaluate_part_train_ready(specimen_id, part_id, ref.get("reslice_id", ""))
            )
            if action in {"prepare_dataset", "train"} and not readiness["train_ready"]:
                raise ValueError(f"part_not_train_ready:{specimen_id}:{part_id}:{','.join(readiness['reasons'])}")
            if action == "predict" and not readiness["predict_ready"]:
                raise ValueError(f"part_not_predict_ready:{specimen_id}:{part_id}:{','.join(readiness['reasons'])}")
            samples.append(self._contract_part_sample(specimen, part, readiness, include_label=action in {"prepare_dataset", "train"}))
        return samples

    def _contract_part_sample(self, specimen, part, readiness, include_label=True):
        reslice_id = readiness.get("reslice_id", "")
        reslice = self.project_manager.get_part_reslice(specimen.get("specimen_id"), part.get("part_id"), reslice_id, default={}) or {}
        manual = readiness.get("label_record") or self.project_manager.part_label_record(
            specimen.get("specimen_id"),
            part.get("part_id"),
            "manual_truth",
            reslice_id=reslice_id,
        )
        include_manual = bool(include_label and manual.get("path"))
        training = part.get("training") or {}
        label_schema_id = str(readiness.get("label_schema_id") or "")
        label_schema = self.project_manager.get_label_schema(label_schema_id, default={}) if label_schema_id else {}
        return {
            "sample_id": _safe_id(f"{specimen.get('specimen_id')}_{part.get('part_id')}_{reslice_id}"),
            "specimen_id": specimen.get("specimen_id"),
            "part_id": part.get("part_id"),
            "user_defined_part_name": training.get("user_defined_part_name") or part.get("display_name") or part.get("part_id"),
            "reslice_id": reslice_id,
            "label_schema_id": label_schema_id,
            "label_schema": label_schema if isinstance(label_schema, dict) else {},
            "input_volume": {
                "path": self.project_manager.to_absolute(reslice.get("image_path", "")),
                "format": "tiff",
                "shape_zyx": readiness.get("input_shape_zyx", []),
                "dtype": str(((reslice.get("outputs") or {}).get("image_dtype")) or ""),
                "spacing_zyx": (reslice.get("reslice_params") or {}).get("output_spacing_zyx")
                or (reslice.get("local_frame") or {}).get("spacing_zyx")
                or (reslice.get("source") or {}).get("part_spacing_zyx")
                or [1.0, 1.0, 1.0],
                "spacing_unit": str((reslice.get("source") or {}).get("part_spacing_unit") or "micrometer"),
                "orientation": "local_axis_reslice",
                "orientation_record": reslice,
            },
            "label_volume": {
                "path": self.project_manager.to_absolute(manual.get("path", "")) if include_manual else "",
                "format": manual.get("format", "") if include_manual else "",
                "role": "manual_truth" if include_manual else "none",
                "shape_zyx": manual.get("shape_zyx", []) if include_manual else [],
                "dtype": manual.get("dtype", "") if include_manual else "",
            },
        }

    def _select_specimens(self, action, specimen_ids):
        ids = [str(item) for item in specimen_ids] if specimen_ids else [item.get("specimen_id") for item in self.project_manager.project_data.get("specimens", [])]
        specimens = []
        for specimen_id in ids:
            specimen = self.project_manager.get_specimen(specimen_id, default=None)
            if specimen is None:
                raise KeyError(f"unknown_specimen_id:{specimen_id}")
            if action in {"prepare_dataset", "train"}:
                readiness = self.project_manager.evaluate_train_ready(specimen_id)
                if not readiness["train_ready"]:
                    raise ValueError(f"specimen_not_train_ready:{specimen_id}:{','.join(readiness['reasons'])}")
            if action == "predict":
                working = specimen.get("working_volume") or {}
                image_path = self.project_manager.to_absolute(working.get("path", ""))
                if not image_path or not volume_sidecar_exists(image_path):
                    raise ValueError(f"specimen_not_predict_ready:{specimen_id}:working_volume_missing")
            specimens.append(self._contract_specimen(specimen, include_label=action in {"prepare_dataset", "train"}))
        return specimens

    def _contract_specimen(self, specimen, include_label):
        working = specimen.get("working_volume") or {}
        manual = (specimen.get("labels") or {}).get("manual_truth") or {}
        return {
            "specimen_id": specimen.get("specimen_id"),
            "modality": specimen.get("modality", "unknown"),
            "input_volume": {
                "path": self.project_manager.to_absolute(working.get("path", "")),
                "format": working.get("format", ""),
                "shape_zyx": working.get("shape_zyx", []),
                "dtype": working.get("dtype", ""),
                "spacing_zyx": working.get("spacing_zyx") or [1.0, 1.0, 1.0],
                "spacing_unit": working.get("spacing_unit", "micrometer"),
                "orientation": working.get("orientation", "unknown"),
            },
            "label_volume": {
                "path": self.project_manager.to_absolute(manual.get("path", "")) if include_label else "",
                "format": manual.get("format", "") if include_label else "",
                "role": "manual_truth" if include_label else "none",
                "shape_zyx": manual.get("shape_zyx", []) if include_label else [],
                "dtype": manual.get("dtype", "") if include_label else "",
            },
            "material_map": self.project_manager.to_absolute(specimen.get("material_map", "")),
        }

    def _artifact_abs_path(self, result, path):
        text = str(path or "")
        if os.path.isabs(text):
            return os.path.normpath(text)
        run_dir = os.path.abspath(os.path.join(self.runs_root, ".."))
        provenance_run_dir = result.get("provenance", {}).get("run_dir")
        if provenance_run_dir:
            run_dir = provenance_run_dir
        elif result.get("run_id"):
            # Best effort: artifacts normally live under the result JSON directory.
            pass
        result_json = result.get("_result_json", "")
        base = os.path.dirname(result_json) if result_json else ""
        if not base:
            base = os.getcwd()
        return os.path.abspath(os.path.join(base, text))

    def _register_run(self, contract, result):
        runs = self.project_manager.project_data.setdefault("runs", [])
        runs.append(
            {
                "run_id": contract.get("run_id"),
                "action": contract.get("action"),
                "backend_id": contract.get("backend_id"),
                "run_dir": contract.get("run_dir"),
                "result_status": result.get("status"),
                "created_at": _now_iso(),
            }
        )
        if contract.get("action") == "train":
            manifest = result.get("provenance", {}).get("model_manifest") or contract.get("model_manifest")
            if manifest:
                self.project_manager.register_tif_segmentation_model_from_manifest(
                    manifest,
                    {
                        "backend_id": contract.get("backend_id"),
                        "run_id": contract.get("run_id"),
                        "run_dir": contract.get("run_dir"),
                        "result_json": contract.get("result_json"),
                        "dataset_manifest": result.get("provenance", {}).get("dataset_manifest", ""),
                        "training_samples": ((result.get("metrics") or {}).get("summary") or {}).get("training_samples", 0),
                        "usable_for_research_prediction": result.get("provenance", {}).get("usable_for_research_prediction", True),
                    },
                    save=False,
                )
        self.project_manager.save_project()

    def _format_template(self, template, run_dir, contract_path):
        return str(template).format(
            python=self.backend_config.get("python_executable", "python"),
            contract=contract_path,
            contract_json=contract_path,
            run_dir=run_dir,
        )

    def _command_environment(self):
        env = os.environ.copy()
        repo_root = _source_repo_root()
        current = str(env.get("PYTHONPATH") or "")
        paths = [repo_root]
        if current:
            paths.append(current)
        env["PYTHONPATH"] = os.pathsep.join(paths)
        return env

    def _run_command(self, command_template, contract_path, run_dir, action, progress_callback=None, cancel_check=None):
        command = self._format_template(command_template, run_dir, contract_path)
        log_dir = os.path.join(run_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, f"{action}_stdout.log")
        stderr_path = os.path.join(log_dir, f"{action}_stderr.log")
        with open(stdout_path, "w", encoding="utf-8") as stdout_handle, open(stderr_path, "w", encoding="utf-8") as stderr_handle:
            started = time.monotonic()
            process = subprocess.Popen(
                command,
                cwd=run_dir,
                shell=True,
                text=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=self._command_environment(),
                start_new_session=os.name != "nt",
            )
            _emit_progress(progress_callback, 0, 0, f"Running {action} command...")
            last_emit = 0.0
            while process.poll() is None:
                if _cancel_requested(cancel_check):
                    _terminate_process_tree(process)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        _kill_process(process)
                        process.wait(timeout=5)
                    _emit_progress(progress_callback, 100, 100, f"Cancelled {action} run.")
                    raise RuntimeError(f"tif_backend_{action}_cancelled:{stdout_path}:{stderr_path}")
                now = time.monotonic()
                if now - last_emit >= 0.5:
                    elapsed = int(now - started)
                    tail = _tail_lines(stdout_path, 4) + _tail_lines(stderr_path, 4)
                    suffix = ""
                    if tail:
                        suffix = "\n" + "\n".join(tail[-6:])
                    _emit_progress(progress_callback, 0, 0, f"Running {action} command... {elapsed}s{suffix}")
                    last_emit = now
                time.sleep(0.1)
            returncode = process.returncode
        if returncode != 0:
            tail = _tail_lines(stderr_path, 10) or _tail_lines(stdout_path, 10)
            suffix = f":{stderr_path}"
            if tail:
                suffix += "\n" + "\n".join(tail[-10:])
            raise RuntimeError(f"tif_backend_{action}_failed:{returncode}{suffix}")
        _emit_progress(progress_callback, 80, 100, f"{action} command finished.")
        return returncode


def write_mock_tif_backend_result(contract, prediction_arrays=None):
    action = contract["action"]
    artifacts = []
    if action == "prepare_dataset":
        manifest_path = os.path.join(contract["output_dir"], "dataset_manifest.json")
        _write_json(
            manifest_path,
            {
                "schema_version": "ant3d_tif_dataset_manifest_v1",
                "specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
            },
        )
        artifacts.append({"type": "dataset_manifest", "path": os.path.relpath(manifest_path, os.path.dirname(contract["result_json"])), "format": "json"})
    elif action == "train":
        manifest_path = contract.get("model_manifest") or os.path.join(contract["output_dir"], "model_manifest.json")
        _write_json(
            manifest_path,
            {
                "schema_version": TIF_MODEL_MANIFEST_SCHEMA_VERSION,
                "model_id": f"{contract['backend_id']}/{contract['run_id']}",
                "backend_id": contract["backend_id"],
                "model_family": contract["training_config"].get("model_family"),
                "created_at": _now_iso(),
                "trained_specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
                "label_role": "manual_truth",
            },
        )
        artifacts.append({"type": "model_manifest", "path": os.path.relpath(manifest_path, os.path.dirname(contract["result_json"])), "format": "json"})
    elif action == "predict":
        if prediction_arrays is None:
            prediction_arrays = {}
        from .tif_volume_io import write_volume_sidecar

        samples = contract.get("part_samples") or contract.get("specimens", [])
        for specimen in samples:
            specimen_id = specimen["specimen_id"]
            part_id = specimen.get("part_id", "")
            input_volume = specimen.get("input_volume", {})
            shape = input_volume.get("shape_zyx", [])
            array = prediction_arrays.get(f"{specimen_id}:{part_id}") if part_id else None
            if array is None:
                array = prediction_arrays.get(specimen_id)
            if array is None:
                import numpy as np

                array = np.zeros(tuple(shape), dtype=np.uint16)
            prediction_id = f"{contract['run_id']}_{_safe_id(specimen_id)}"
            if part_id:
                prediction_id = f"{prediction_id}_{_safe_id(part_id)}"
            out_path = os.path.join(contract["output_dir"], f"{prediction_id}.ome.zarr")
            meta = write_volume_sidecar(out_path, array, role="model_draft", spacing_zyx=input_volume.get("spacing_zyx"), spacing_unit=input_volume.get("spacing_unit", "micrometer"), orientation=input_volume.get("orientation", "unknown"), source_format="mock_tif_backend")
            artifacts.append(
                {
                    "type": "prediction_label_volume",
                    "specimen_id": specimen_id,
                    "part_id": part_id,
                    "reslice_id": specimen.get("reslice_id", ""),
                    "prediction_id": prediction_id,
                    "path": os.path.relpath(out_path, os.path.dirname(contract["result_json"])),
                    "format": meta["format"],
                    "role": "editable_ai_result" if part_id else "model_draft",
                }
            )

    result = {
        "schema_version": TIF_BACKEND_RESULT_SCHEMA_VERSION,
        "contract_schema_version": TIF_BACKEND_CONTRACT_SCHEMA_VERSION,
        "status": "success",
        "action": action,
        "backend_id": contract["backend_id"],
        "run_id": contract["run_id"],
        "artifacts": artifacts,
        "metrics": {"summary": {}, "by_material": {}},
        "warnings": [],
        "errors": [],
        "provenance": {
            "started_at": _now_iso(),
            "finished_at": _now_iso(),
            "model_manifest": contract.get("model_manifest", ""),
            "input_specimens": [item["specimen_id"] for item in contract.get("specimens", [])],
            "input_part_samples": [
                {
                    "specimen_id": item.get("specimen_id"),
                    "part_id": item.get("part_id"),
                    "reslice_id": item.get("reslice_id"),
                }
                for item in contract.get("part_samples", [])
            ],
            "input_label_role": "manual_truth" if action in {"prepare_dataset", "train"} else "none",
        },
    }
    _write_json(contract["result_json"], result)
    return result
