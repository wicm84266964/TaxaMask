from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / "AntSleap" / "main.py"
ARCHITECTURE_PATHS = (
    MAIN_PATH,
    ROOT / "AntSleap" / "ui" / "main_window_workers.py",
    ROOT / "AntSleap" / "ui" / "main_window_widgets.py",
    ROOT / "AntSleap" / "ui" / "main_window_dialogs.py",
    ROOT / "AntSleap" / "ui" / "training_report_dialogs.py",
    ROOT / "AntSleap" / "ui" / "route_management_panel.py",
    ROOT / "AntSleap" / "ui" / "settings_dialogs.py",
    ROOT / "AntSleap" / "ui" / "model_settings_dialog.py",
    ROOT / "AntSleap" / "ui" / "model_settings_view.py",
    ROOT / "AntSleap" / "ui" / "model_settings_dataset.py",
    ROOT / "AntSleap" / "ui" / "model_settings_profile.py",
    ROOT / "AntSleap" / "ui" / "model_settings_agent.py",
    ROOT / "AntSleap" / "ui" / "main_window_shell.py",
    ROOT / "AntSleap" / "ui" / "main_window_start_center.py",
    ROOT / "AntSleap" / "ui" / "main_window_agent_context.py",
    ROOT / "AntSleap" / "ui" / "main_window_signal_router.py",
    ROOT / "AntSleap" / "ui" / "main_window_coordinator.py",
    ROOT / "AntSleap" / "ui" / "main_window_project_lifecycle.py",
)
KEY_TEST_PATHS = (
    ROOT / "tests" / "test_blink_bridge.py",
    ROOT / "tests" / "test_gui_smoke.py",
    ROOT / "tests" / "test_reporting_routes.py",
    ROOT / "tests" / "test_ui_localization.py",
    ROOT / "tests" / "test_ui_polish_scope.py",
)

WORKFLOW_PATTERNS = (
    ("runtime_worker", 1, re.compile(r"runtime|thread|worker|inference|export|import_thread|no_wheel|drag|drop", re.I)),
    ("vlm_prediction_export", 7, re.compile(r"vlm|predict|draft|batch_inference|dataset_export|auto_box", re.I)),
    ("blink", 6, re.compile(r"blink|shrink|expert|parent_context|child", re.I)),
    ("dialog_settings", 2, re.compile(r"dialog|settings|route|profile|report|preflight|literature", re.I)),
    ("shell_start_agent", 3, re.compile(r"start_|agent|workflow|theme|language|menu|tab|window|console", re.I)),
    ("project_lifecycle", 4, re.compile(r"project|sqlite|migration|backup|relocat|open_|close|save_timer|flush_pending", re.I)),
    ("image_navigation", 5, re.compile(r"image|file_list|part_tree|taxonomy|panel_split|crop|group|description|genus", re.I)),
    ("annotation_sam", 6, re.compile(r"annot|polygon|magic|sam|canvas|measure|scale|tool", re.I)),
    ("training_model", 7, re.compile(r"train|model|locator|segmenter", re.I)),
    ("tif_integration", 3, re.compile(r"tif|volume", re.I)),
    ("pdf_evidence", 5, re.compile(r"pdf|literature", re.I)),
)

CLASS_STAGE_OVERRIDES = {
    "InferenceThread": 1,
    "VlmPreannotationThread": 1,
    "DatasetExportThread": 1,
    "ImageImportThread": 1,
    "ExternalBatchInferenceThread": 1,
    "ExternalTrainingThread": 1,
    "NoWheelComboBox": 1,
    "NoWheelSpinBox": 1,
    "NoWheelSlider": 1,
    "ImageGroupListWidget": 1,
    "TrainingThread": 1,
    "TrainingPreflightDialog": 2,
    "TrainingReportDialog": 2,
    "TrainingResultBrowserDialog": 2,
    "RouteManagementPanel": 2,
    "ModelSettingsDialog": 2,
    "GeneralSettingsDialog": 2,
    "TifModelSettingsDialog": 2,
    "ExportDialog": 2,
    "BlinkEntryDialog": 2,
    "LiteratureDescriptionDialog": 2,
    "MainWindow": 3,
}

PUBLIC_MAIN_WINDOW_METHODS = {
    "change_language",
    "change_theme",
    "closeEvent",
    "enter_image_workflow",
    "enter_tif_workflow",
    "launch_blink_from_workbench",
    "open_agent_from_context",
    "open_general_settings",
    "open_project",
    "open_project_path",
    "open_settings",
    "open_stl_model_settings",
    "open_tif_model_settings",
    "refresh_ui",
    "return_to_start_center_with_context",
    "run_prediction",
    "run_training",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source_segment(node: ast.AST) -> str:
    try:
        return " ".join(ast.unparse(node).split())
    except (AttributeError, ValueError):
        return ""


def _workflow_for(name: str) -> tuple[str, int]:
    for workflow, stage, pattern in WORKFLOW_PATTERNS:
        if pattern.search(name):
            return workflow, stage
    return "unclassified", 8


def _class_nodes(tree: ast.Module) -> list[ast.ClassDef]:
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


def _method_nodes(class_node: ast.ClassDef) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _python_files() -> list[Path]:
    roots = (ROOT / "AntSleap", ROOT / "core", ROOT / "tools", ROOT / "tests", ROOT / "scripts")
    paths: set[Path] = set()
    for root in roots:
        if root.exists():
            paths.update(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(paths)


def _reference_inventory(names: set[str]) -> dict[str, list[dict[str, object]]]:
    references: dict[str, list[dict[str, object]]] = defaultdict(list)
    if not names:
        return references
    pattern = re.compile(r"\b(" + "|".join(sorted((re.escape(name) for name in names), key=len, reverse=True)) + r")\b")
    for path in _python_files():
        if path == MAIN_PATH:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(_read(path).splitlines(), 1):
            for name in set(pattern.findall(line)):
                references[name].append(
                    {
                        "file": relative,
                        "line": line_number,
                        "text": line.strip()[:240],
                        "is_test": relative.startswith("tests/"),
                    }
                )
    return references


def _enclosing_owner(classes: list[ast.ClassDef], line: int) -> tuple[str, str]:
    for class_node in classes:
        if class_node.lineno <= line <= class_node.end_lineno:
            for method in _method_nodes(class_node):
                if method.lineno <= line <= method.end_lineno:
                    return class_node.name, method.name
            return class_node.name, "<class_body>"
    return "<module>", "<module>"


def _connections(tree: ast.Module, classes: list[ast.ClassDef], source_path: Path = MAIN_PATH) -> list[dict[str, object]]:
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr not in {"connect", "connect_once"}:
            continue
        if node.func.attr == "connect_once":
            signal = _source_segment(node.args[1]) if len(node.args) > 1 else ""
            target = _source_segment(node.args[2]) if len(node.args) > 2 else ""
        else:
            signal = _source_segment(node.func.value)
            target = _source_segment(node.args[0]) if node.args else ""
        owner_class, owner_method = _enclosing_owner(classes, node.lineno)
        if owner_class == "MainWindowSignalRouter" and node.func.attr == "connect":
            continue
        workflow, stage = _workflow_for(f"{owner_class} {owner_method} {signal} {target}")
        rows.append(
            {
                "file": source_path.relative_to(ROOT).as_posix(),
                "line": node.lineno,
                "binding": node.func.attr,
                "owner_class": owner_class,
                "owner_method": owner_method,
                "signal": signal,
                "target": target,
                "workflow": workflow,
                "target_stage": stage,
            }
        )
    return sorted(rows, key=lambda row: (str(row["file"]), int(row["line"])))


def _async_inventory(tree: ast.Module, classes: list[ast.ClassDef], source_path: Path = MAIN_PATH) -> list[dict[str, object]]:
    rows = []
    patterns = {
        "QThread": re.compile(r"(?:^|\.)QThread$"),
        "python_thread": re.compile(r"threading\.Thread$"),
        "single_shot": re.compile(r"QTimer\.singleShot$"),
        "thread_start": re.compile(r"\.start$"),
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = _source_segment(node.func)
        kind = next((name for name, pattern in patterns.items() if pattern.search(call)), "")
        if not kind:
            continue
        owner_class, owner_method = _enclosing_owner(classes, node.lineno)
        workflow, stage = _workflow_for(f"{owner_class} {owner_method} {call}")
        rows.append(
            {
                "file": source_path.relative_to(ROOT).as_posix(),
                "line": node.lineno,
                "kind": kind,
                "call": call,
                "owner_class": owner_class,
                "owner_method": owner_method,
                "workflow": workflow,
                "target_stage": stage,
            }
        )
    return sorted(rows, key=lambda row: (str(row["file"]), int(row["line"])))


def _self_attribute_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr
    return ""


def _state_inventory(main_window: ast.ClassDef) -> tuple[list[dict[str, object]], int]:
    rows: dict[str, dict[str, object]] = {}
    occurrences = 0
    for node in ast.walk(main_window):
        targets: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            raw_targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            targets.extend(raw_targets)
        for target in targets:
            candidates = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
            for candidate in candidates:
                name = _self_attribute_name(candidate)
                if not name:
                    continue
                occurrences += 1
                row = rows.setdefault(name, {"field": name, "assignments": 0, "lines": []})
                row["assignments"] = int(row["assignments"]) + 1
                row["lines"].append(node.lineno)
    return sorted(rows.values(), key=lambda row: str(row["field"])), occurrences


def _main_import_inventory() -> list[dict[str, object]]:
    patterns = (
        re.compile(r"\bfrom\s+(?:AntSleap\.)?main\s+import\b"),
        re.compile(r"\bimport\s+(?:AntSleap\.)?main\b"),
        re.compile(r"\bfrom\s+AntSleap\s+import\s+main\b"),
    )
    rows = []
    for path in _python_files():
        if path == MAIN_PATH:
            continue
        relative = path.relative_to(ROOT).as_posix()
        for line_number, line in enumerate(_read(path).splitlines(), 1):
            if any(pattern.search(line) for pattern in patterns):
                rows.append({"file": relative, "line": line_number, "text": line.strip()})
    return rows


def _key_test_reference_inventory() -> tuple[list[dict[str, object]], Counter[str]]:
    rows = []
    private_refs: Counter[str] = Counter()
    direct_pattern = re.compile(r"main_module\.|\bMainWindow\.|\bfrom\s+(?:AntSleap\.)?main\s+import\b|\bfrom\s+AntSleap\s+import\s+main\b")
    private_pattern = re.compile(r"\b(?:window|fake_window|main_window|main_module\.MainWindow|MainWindow)\.(_[A-Za-z0-9_]+)")
    for path in KEY_TEST_PATHS:
        text = _read(path)
        for line_number, line in enumerate(text.splitlines(), 1):
            refs = private_pattern.findall(line)
            private_refs.update(refs)
            if direct_pattern.search(line) or refs:
                rows.append(
                    {
                        "file": path.relative_to(ROOT).as_posix(),
                        "line": line_number,
                        "text": line.strip()[:240],
                        "private_refs": sorted(set(refs)),
                    }
                )
    return rows, private_refs


def build_report() -> dict[str, object]:
    text = _read(MAIN_PATH)
    tree = ast.parse(text)
    classes = _class_nodes(tree)
    main_window = next(node for node in classes if node.name == "MainWindow")
    all_methods = [method for class_node in classes for method in _method_nodes(class_node)]
    main_methods = _method_nodes(main_window)
    names = {node.name for node in classes} | {node.name for node in all_methods}
    references = _reference_inventory(names)
    architecture_modules = {}
    for path in ARCHITECTURE_PATHS:
        if path.exists():
            module_tree = ast.parse(_read(path))
            architecture_modules[path] = (module_tree, _class_nodes(module_tree))
    connections = [
        row
        for path, (module_tree, module_classes) in architecture_modules.items()
        for row in _connections(module_tree, module_classes, path)
    ]
    async_rows = [
        row
        for path, (module_tree, module_classes) in architecture_modules.items()
        for row in _async_inventory(module_tree, module_classes, path)
    ]
    main_source = MAIN_PATH.relative_to(ROOT).as_posix()
    state_rows, main_window_state_assignments = _state_inventory(main_window)
    import_rows = _main_import_inventory()
    key_test_rows, private_test_refs = _key_test_reference_inventory()

    class_rows = []
    for class_node in classes:
        methods = _method_nodes(class_node)
        stage = CLASS_STAGE_OVERRIDES.get(class_node.name, _workflow_for(class_node.name)[1])
        class_rows.append(
            {
                "name": class_node.name,
                "line": class_node.lineno,
                "end_line": class_node.end_lineno,
                "size": class_node.end_lineno - class_node.lineno + 1,
                "method_count": len(methods),
                "connection_count": sum(
                    row["file"] == main_source and class_node.lineno <= int(row["line"]) <= class_node.end_lineno
                    for row in connections
                ),
                "reference_count": len(references.get(class_node.name, [])),
                "target_stage": stage,
                "references": references.get(class_node.name, []),
            }
        )

    method_rows = []
    for method in main_methods:
        workflow, stage = _workflow_for(method.name)
        refs = references.get(method.name, [])
        source_refs = [row for row in refs if not row["is_test"]]
        test_refs = [row for row in refs if row["is_test"]]
        signal_refs = [row for row in connections if str(row["target"]).endswith(f".{method.name}")]
        if method.name in PUBLIC_MAIN_WINDOW_METHODS or source_refs:
            compatibility = "public_or_source_compatibility"
        elif signal_refs:
            compatibility = "signal_compatibility"
        elif test_refs:
            compatibility = "test_compatibility"
        else:
            compatibility = "internal_or_unreferenced"
        method_rows.append(
            {
                "name": method.name,
                "line": method.lineno,
                "end_line": method.end_lineno,
                "size": method.end_lineno - method.lineno + 1,
                "workflow": workflow,
                "target_stage": stage,
                "compatibility": compatibility,
                "source_ref_count": len(source_refs),
                "test_ref_count": len(test_refs),
                "signal_ref_count": len(signal_refs),
                "references": refs,
            }
        )

    init_method = next(node for node in main_methods if node.name == "__init__")
    source_state_assignment_lines = len(re.findall(r"^\s*self\.[A-Za-z_][A-Za-z0-9_]*\s*=", text, re.MULTILINE))
    metrics = {
        "main_physical_lines": text.count("\n") + 1,
        "top_level_class_count": len(classes),
        "top_level_function_count": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in tree.body),
        "all_method_count": len(all_methods),
        "private_method_count": sum(method.name.startswith("_") for method in all_methods),
        "connection_count": len(connections),
        "source_state_assignment_lines": source_state_assignment_lines,
        "main_window_lines": main_window.end_lineno - main_window.lineno + 1,
        "main_window_method_count": len(main_methods),
        "main_window_connection_count": sum(
            row["file"] == main_source and main_window.lineno <= int(row["line"]) <= main_window.end_lineno
            for row in connections
        ),
        "main_window_init_lines": init_method.end_lineno - init_method.lineno + 1,
        "main_window_methods_ge_50": sum(row["size"] >= 50 for row in method_rows),
        "main_window_methods_ge_100": sum(row["size"] >= 100 for row in method_rows),
        "main_window_unique_state_fields": len(state_rows),
        "main_window_state_assignment_occurrences": main_window_state_assignments,
        "main_import_site_count": len(import_rows),
        "key_test_reference_line_count": len(key_test_rows),
        "key_test_private_reference_occurrences": sum(private_test_refs.values()),
        "key_test_unique_private_references": len(private_test_refs),
        "async_entry_count": len(async_rows),
    }
    return {
        "source": MAIN_PATH.relative_to(ROOT).as_posix(),
        "metrics": metrics,
        "workflow_method_counts": dict(Counter(row["workflow"] for row in method_rows)),
        "stage_method_counts": dict(Counter(str(row["target_stage"]) for row in method_rows)),
        "compatibility_counts": dict(Counter(row["compatibility"] for row in method_rows)),
        "classes": class_rows,
        "main_window_methods": method_rows,
        "connections": connections,
        "async_entries": async_rows,
        "state_fields": state_rows,
        "main_imports": import_rows,
        "key_test_references": key_test_rows,
        "private_test_references": dict(private_test_refs.most_common()),
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return output


def render_method_inventory(report: dict[str, object]) -> str:
    metrics = report["metrics"]
    lines = [
        "# TaxaMask Round 4 Main Window Method Inventory",
        "",
        "由 `scripts/analyze_main_window_architecture.py` 生成。Stage 0 冻结当前责任、兼容入口和目标阶段，实施时必须结合真实调用复核。",
        "",
        "## Metrics",
        "",
    ]
    lines.extend(_markdown_table(["Metric", "Value"], [[key, value] for key, value in metrics.items()]))
    lines.extend(["", "## Top-level Classes", ""])
    lines.extend(
        _markdown_table(
            ["Line", "Size", "Class", "Methods", "Connects", "Refs", "Stage"],
            [
                [row["line"], row["size"], f"`{row['name']}`", row["method_count"], row["connection_count"], row["reference_count"], row["target_stage"]]
                for row in report["classes"]
            ],
        )
    )
    lines.extend(["", "## MainWindow Workflow Counts", ""])
    lines.extend(_markdown_table(["Workflow", "Methods"], sorted(report["workflow_method_counts"].items())))
    lines.extend(["", "## Compatibility Counts", ""])
    lines.extend(_markdown_table(["Compatibility", "Methods"], sorted(report["compatibility_counts"].items())))
    lines.extend(["", "## MainWindow Methods", ""])
    lines.extend(
        _markdown_table(
            ["Line", "Size", "Method", "Workflow", "Stage", "Compatibility", "Source refs", "Test refs", "Signal refs"],
            [
                [
                    row["line"], row["size"], f"`{row['name']}`", row["workflow"], row["target_stage"], row["compatibility"],
                    row["source_ref_count"], row["test_ref_count"], row["signal_ref_count"],
                ]
                for row in report["main_window_methods"]
            ],
        )
    )
    lines.extend(["", "## MainWindow State Fields", ""])
    lines.extend(
        _markdown_table(
            ["Field", "Assignments", "Lines", "Target owner", "Stage"],
            [[f"`{row['field']}`", row["assignments"], ", ".join(str(value) for value in row["lines"]), "TBD", "TBD"] for row in report["state_fields"]],
        )
    )
    lines.extend(["", "## Main Import Compatibility", ""])
    lines.extend(
        _markdown_table(
            ["File", "Line", "Import"],
            [[row["file"], row["line"], f"`{row['text']}`"] for row in report["main_imports"]],
        )
    )
    lines.extend(["", "## Key Test Dependencies", ""])
    lines.extend(
        _markdown_table(
            ["File", "Line", "Reference", "Private refs", "Migration target"],
            [
                [row["file"], row["line"], f"`{row['text']}`", ", ".join(f"`{name}`" for name in row["private_refs"]) or "-", "TBD"]
                for row in report["key_test_references"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def render_signal_inventory(report: dict[str, object]) -> str:
    lines = [
        "# TaxaMask Round 4 Main Window Signal and Async Inventory",
        "",
        "由 `scripts/analyze_main_window_architecture.py` 生成。目标 owner、解绑策略和 contract test 在对应 Stage 实施前填写。",
        "",
        "## Qt Connections",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["File", "Line", "Binding", "Owner", "Signal", "Current target", "Workflow", "Stage", "Target owner", "Unbind", "Contract test"],
            [
                [
                    row["file"], row["line"], row["binding"], f"`{row['owner_class']}.{row['owner_method']}`", f"`{row['signal']}`", f"`{row['target']}`" if row["target"] else "-",
                    row["workflow"], row["target_stage"], "TBD", "TBD", "TBD",
                ]
                for row in report["connections"]
            ],
        )
    )
    lines.extend(["", "## Thread Timer and Async Entries", ""])
    lines.extend(
        _markdown_table(
            ["File", "Line", "Kind", "Owner", "Call", "Workflow", "Stage", "Cancel/cleanup", "Context guard"],
            [
                [
                    row["file"], row["line"], row["kind"], f"`{row['owner_class']}.{row['owner_method']}`", f"`{row['call']}`",
                    row["workflow"], row["target_stage"], "TBD", "TBD",
                ]
                for row in report["async_entries"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit TaxaMask main.py and MainWindow architecture coupling.")
    parser.add_argument("--json", type=Path, help="Write the full machine-readable report.")
    parser.add_argument("--method-ledger", type=Path, help="Write the method, state, import, and test ledger.")
    parser.add_argument("--signal-ledger", type=Path, help="Write the signal and async ledger.")
    parser.add_argument("--summary", action="store_true", help="Print summary metrics as JSON.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.method_ledger:
        args.method_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.method_ledger.write_text(render_method_inventory(report), encoding="utf-8")
    if args.signal_ledger:
        args.signal_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.signal_ledger.write_text(render_signal_inventory(report), encoding="utf-8")
    if args.summary or not any((args.json, args.method_ledger, args.signal_ledger)):
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
