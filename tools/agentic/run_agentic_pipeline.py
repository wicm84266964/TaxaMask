import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from typing import Any


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", ".."))
DEFAULT_CONTRACT = os.path.join(REPO_ROOT, "AntSleap", "config", "agentic_pipeline_contract.json")


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_not_object:{path}")
    return payload


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_json(path: str, payload: dict[str, Any]) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _resolve_repo_path(path: str) -> str:
    if not path:
        return ""
    expanded = os.path.expanduser(os.path.expandvars(path))
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    return os.path.normpath(os.path.join(REPO_ROOT, expanded))


def _contract_inputs(contract: dict[str, Any], overrides: dict[str, str]) -> dict[str, dict[str, Any]]:
    inputs: dict[str, dict[str, Any]] = {}
    for item in contract.get("required_inputs", []):
        if not isinstance(item, dict):
            continue
        input_id = str(item.get("id", "")).strip()
        if not input_id:
            continue
        raw_value = str(overrides.get(input_id) or item.get("default", "") or "").strip()
        resolved = _resolve_repo_path(raw_value) if raw_value else ""
        kind = str(item.get("kind", "file") or "file")
        exists = bool(resolved and os.path.exists(resolved))
        if kind == "directory" and resolved:
            exists = os.path.isdir(resolved)
        elif kind == "file" and resolved:
            exists = os.path.isfile(resolved)
        inputs[input_id] = {
            "id": input_id,
            "kind": kind,
            "configured_value": raw_value,
            "resolved_path": resolved,
            "exists": exists,
            "description": str(item.get("description", "") or ""),
        }
    return inputs


def _refresh_input_existence(inputs: dict[str, dict[str, Any]]) -> None:
    for payload in inputs.values():
        resolved = str(payload.get("resolved_path", "") or "")
        kind = str(payload.get("kind", "file") or "file")
        exists = bool(resolved and os.path.exists(resolved))
        if kind == "directory" and resolved:
            exists = os.path.isdir(resolved)
        elif kind == "file" and resolved:
            exists = os.path.isfile(resolved)
        payload["exists"] = exists


def _token_values(inputs: dict[str, dict[str, Any]], output_dir: str) -> dict[str, str]:
    values = {
        "python": sys.executable,
        "repo_root": REPO_ROOT,
        "output_dir": output_dir,
    }
    for input_id, payload in inputs.items():
        values[input_id] = str(payload.get("resolved_path", "") or "")
    return values


def _render_text(text: str, values: dict[str, str]) -> str:
    rendered = str(text)
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def _render_list(items: list[Any], values: dict[str, str]) -> list[str]:
    return [_render_text(str(item), values) for item in items]


def _stage_plan(stage: dict[str, Any], inputs: dict[str, dict[str, Any]], values: dict[str, str], allow_model_inference: bool = False) -> dict[str, Any]:
    required_input_ids = [str(item) for item in stage.get("required_inputs", [])]
    missing_inputs = [
        input_id
        for input_id in required_input_ids
        if input_id not in inputs or not bool(inputs[input_id].get("exists", False))
    ]
    autonomy_level = str(stage.get("autonomy_level", "") or "")
    execution_type = str(stage.get("execution_type", "") or "")
    command = stage.get("command", [])
    rendered_command = _render_list(command, values) if isinstance(command, list) else []

    blocked_reasons: list[str] = []
    if missing_inputs:
        blocked_reasons.append("missing_inputs:" + ",".join(missing_inputs))
    if autonomy_level in {"needs_headless_wrapper", "missing_adapter", "needs_small_cli", "ready_after_adapters"}:
        blocked_reasons.append("adapter_not_implemented:" + autonomy_level)
    if autonomy_level == "ready_model_gated" and not allow_model_inference:
        blocked_reasons.append("model_inference_requires_allow_model_inference")
    if execution_type == "command" and not rendered_command:
        blocked_reasons.append("command_not_configured")
    if execution_type not in {"command", "agent_internal"} and autonomy_level == "ready":
        blocked_reasons.append("non_command_ready_stage_requires_agent_implementation")

    rendered_outputs = _render_list(stage.get("outputs", []), values) if isinstance(stage.get("outputs", []), list) else []
    return {
        "stage_id": str(stage.get("id", "") or ""),
        "title": str(stage.get("title", "") or ""),
        "autonomy_level": autonomy_level,
        "execution_type": execution_type,
        "required_inputs": required_input_ids,
        "missing_inputs": missing_inputs,
        "command": rendered_command,
        "outputs": rendered_outputs,
        "gates": stage.get("gates", []),
        "agent_notes": str(stage.get("agent_notes", "") or ""),
        "runnable": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "execution_result": None,
    }


def _run_command(command: list[str]) -> dict[str, Any]:
    process = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    output = (process.stdout or "") + (process.stderr or "")
    return {
        "exit_code": int(process.returncode),
        "ok": process.returncode == 0,
        "output": output.strip(),
    }


def build_plan(contract: dict[str, Any], inputs: dict[str, dict[str, Any]], output_dir: str, allow_model_inference: bool = False) -> dict[str, Any]:
    values = _token_values(inputs, output_dir)
    stages = [
        _stage_plan(stage, inputs, values, allow_model_inference=allow_model_inference)
        for stage in contract.get("stages", [])
        if isinstance(stage, dict)
    ]
    counts: dict[str, int] = {}
    for stage in stages:
        key = str(stage.get("autonomy_level", "unknown") or "unknown")
        counts[key] = counts.get(key, 0) + 1

    return {
        "schema_version": "formica-agentic-run-plan-v1",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "repo_root": REPO_ROOT,
        "contract_schema_version": str(contract.get("schema_version", "") or ""),
        "assumptions": contract.get("assumptions", {}),
        "readiness_summary": contract.get("readiness_summary", {}),
        "inputs": inputs,
        "stage_counts_by_autonomy": counts,
        "stages": stages,
        "non_negotiable_controls": contract.get("non_negotiable_controls", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or execute the Formica-Flow agentic pipeline plan.")
    parser.add_argument("--contract", default=DEFAULT_CONTRACT, help="Agentic pipeline contract JSON path.")
    parser.add_argument("--out", default=os.path.join(REPO_ROOT, "artifacts", "agentic_pipeline"), help="Output artifact directory.")
    parser.add_argument("--pdf-source-dir", default="", help="Override input pdf_source_dir.")
    parser.add_argument("--project", default="", help="Override input project path.")
    parser.add_argument("--db", default="", help="Override input db path.")
    parser.add_argument("--policy", default="", help="Override input policy path.")
    parser.add_argument("--dry-run", action="store_true", help="Only write the run plan; this is the default.")
    parser.add_argument("--execute-ready", action="store_true", help="Execute currently runnable command stages in order.")
    parser.add_argument("--allow-model-inference", action="store_true", help="Allow runnable stages that initialize model weights/GPU inference.")
    args = parser.parse_args()

    contract_path = _resolve_repo_path(args.contract)
    contract = _load_json(contract_path)
    output_dir = _resolve_repo_path(args.out)
    _ensure_dir(output_dir)

    overrides = {
        "pdf_source_dir": args.pdf_source_dir,
        "project": args.project,
        "db": args.db,
        "policy": args.policy,
        "output_dir": args.out,
    }
    inputs = _contract_inputs(contract, overrides)
    if "output_dir" in inputs:
        inputs["output_dir"]["resolved_path"] = output_dir
        inputs["output_dir"]["exists"] = True

    plan = build_plan(contract, inputs, output_dir, allow_model_inference=bool(args.allow_model_inference))
    plan["mode"] = "execute_ready" if args.execute_ready else "dry_run"

    if args.execute_ready:
        contract_stages = [stage for stage in contract.get("stages", []) if isinstance(stage, dict)]
        for index, raw_stage in enumerate(contract_stages):
            _refresh_input_existence(inputs)
            refreshed_stage = _stage_plan(
                raw_stage,
                inputs,
                _token_values(inputs, output_dir),
                allow_model_inference=bool(args.allow_model_inference),
            )
            refreshed_stage["execution_result"] = plan["stages"][index].get("execution_result")
            plan["stages"][index] = refreshed_stage
            stage = plan["stages"][index]
            if not bool(stage.get("runnable", False)):
                continue
            command = stage.get("command", [])
            if not isinstance(command, list) or not command:
                continue
            result = _run_command(command)
            stage["execution_result"] = result
            if not bool(result.get("ok", False)):
                plan["status"] = "failed"
                plan["failed_stage"] = stage.get("stage_id")
                break
        else:
            plan["status"] = "executed_ready_stages"
            plan["failed_stage"] = None
        _refresh_input_existence(inputs)
        for index, raw_stage in enumerate(contract_stages):
            previous_result = plan["stages"][index].get("execution_result")
            refreshed_stage = _stage_plan(
                raw_stage,
                inputs,
                _token_values(inputs, output_dir),
                allow_model_inference=bool(args.allow_model_inference),
            )
            refreshed_stage["execution_result"] = previous_result
            plan["stages"][index] = refreshed_stage
    else:
        plan["status"] = "dry_run"
        plan["failed_stage"] = None

    run_plan_path = os.path.join(output_dir, "agentic_run_plan.json")
    _write_json(run_plan_path, plan)

    runnable_count = sum(1 for stage in plan["stages"] if bool(stage.get("runnable", False)))
    blocked_count = len(plan["stages"]) - runnable_count
    print(f"status={plan['status']}")
    print(f"runnable_stages={runnable_count}")
    print(f"blocked_stages={blocked_count}")
    print(f"run_plan={run_plan_path}")

    if args.execute_ready and plan.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
