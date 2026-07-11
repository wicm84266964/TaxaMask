from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKBENCH_PATH = ROOT / "AntSleap" / "ui" / "tif_workbench.py"
DEFAULT_TEST_PATHS = (
    ROOT / "tests" / "test_tif_workbench.py",
    ROOT / "tests" / "test_gui_smoke.py",
    ROOT / "tests" / "test_ui_polish_scope.py",
)

WORKFLOW_PATTERNS = (
    ("selection_lifecycle", re.compile(r"project|specimen|selection|select_|load_specimen|load_part|refresh_project|close_project", re.I)),
    ("annotation_save_truth", re.compile(r"label|annot|brush|contour|edit|save|dirty|truth|promote", re.I)),
    ("roi_to_part", re.compile(r"roi|region", re.I)),
    ("part_mask_material", re.compile(r"part_mask|mask_key|material|interpolat", re.I)),
    ("volume_preview_render", re.compile(r"preview|render|volume|gpu|slice|overlay|transfer|camera", re.I)),
    ("local_axis_reslice", re.compile(r"local_axis|reslice|roll_reference", re.I)),
    ("backend_result_review", re.compile(r"backend|train|predict|model|result|comparison", re.I)),
    ("task_lifecycle", re.compile(r"task|thread|busy|lock|cleanup|cancel|progress", re.I)),
    ("shell_view_text", re.compile(r"layout|text|tooltip|style|button|control|panel|tab|status|lang", re.I)),
    ("import_export", re.compile(r"import|export|manifest", re.I)),
)

PUBLIC_METHOD_NAMES = {
    "close_project",
    "get_agent_context",
    "open_project",
    "refresh_project",
    "set_language",
    "set_theme",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source_segment(text: str, node: ast.AST) -> str:
    try:
        return " ".join(ast.unparse(node).split())
    except (AttributeError, ValueError):
        return ""


def _workflow_for(name: str) -> str:
    matches = [workflow for workflow, pattern in WORKFLOW_PATTERNS if pattern.search(name)]
    return matches[0] if matches else "unclassified"


def _method_nodes(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    widget = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TifWorkbenchWidget"
    )
    return [
        node
        for node in widget.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _call_target(call: ast.Call, text: str) -> str:
    if call.args:
        return _source_segment(text, call.args[0])
    return ""


def _connections(tree: ast.Module, text: str) -> list[dict[str, object]]:
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "connect":
            continue
        signal = _source_segment(text, node.func.value)
        target = _call_target(node, text)
        rows.append(
            {
                "line": node.lineno,
                "signal": signal,
                "target": target,
                "workflow": _workflow_for(f"{signal} {target}"),
            }
        )
    return sorted(rows, key=lambda row: int(row["line"]))


def _test_inventory(paths: tuple[Path, ...]) -> tuple[list[dict[str, object]], Counter]:
    rows = []
    private_counter: Counter[str] = Counter()
    private_pattern = re.compile(r"\b(?:widget|workbench|self\.widget|self\.workbench)\.(_[A-Za-z0-9_]+)")
    class_pattern = re.compile(r"TifWorkbenchWidget\.(_[A-Za-z0-9_]+)")
    for path in paths:
        text = _read(path)
        source_lines = text.splitlines(keepends=True)
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            source = "".join(source_lines[node.lineno - 1 : node.end_lineno])
            refs = private_pattern.findall(source) + class_pattern.findall(source)
            for ref in refs:
                private_counter[ref] += 1
            rows.append(
                {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": node.lineno,
                    "test": node.name,
                    "workflow": _workflow_for(node.name),
                    "private_refs": sorted(set(refs)),
                    "private_ref_count": len(refs),
                    "target_layer": "gui_key_path" if not refs else "workflow_controller",
                }
            )
    return sorted(rows, key=lambda row: (str(row["file"]), int(row["line"]))), private_counter


def _python_files() -> list[Path]:
    roots = (ROOT / "AntSleap", ROOT / "core", ROOT / "tests", ROOT / "scripts")
    paths = []
    for root in roots:
        if not root.exists():
            continue
        paths.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(set(paths))


def _method_references(method_names: set[str]) -> dict[str, list[dict[str, object]]]:
    references: dict[str, list[dict[str, object]]] = defaultdict(list)
    pattern = re.compile(r"\.(_?[A-Za-z][A-Za-z0-9_]*)\b")
    for path in _python_files():
        if path == WORKBENCH_PATH:
            continue
        for line_number, line in enumerate(_read(path).splitlines(), 1):
            for name in pattern.findall(line):
                if name not in method_names:
                    continue
                references[name].append(
                    {
                        "file": path.relative_to(ROOT).as_posix(),
                        "line": line_number,
                        "text": line.strip()[:240],
                    }
                )
    return references


def build_report() -> dict[str, object]:
    text = _read(WORKBENCH_PATH)
    tree = ast.parse(text)
    methods = _method_nodes(tree)
    method_names = {node.name for node in methods}
    references = _method_references(method_names)
    connections = _connections(tree, text)
    tests, private_counter = _test_inventory(DEFAULT_TEST_PATHS)

    method_rows = []
    for node in methods:
        size = node.end_lineno - node.lineno + 1
        refs = references.get(node.name, [])
        external_source_refs = [row for row in refs if not str(row["file"]).startswith("tests/")]
        test_refs = [row for row in refs if str(row["file"]).startswith("tests/")]
        signal_refs = [row for row in connections if str(row["target"]).endswith(f".{node.name}")]
        if node.name in PUBLIC_METHOD_NAMES or external_source_refs:
            compatibility = "public_compatibility"
        elif signal_refs:
            compatibility = "signal_compatibility"
        elif test_refs:
            compatibility = "test_compatibility"
        else:
            compatibility = "internal_or_unreferenced"
        method_rows.append(
            {
                "name": node.name,
                "line": node.lineno,
                "size": size,
                "workflow": _workflow_for(node.name),
                "compatibility": compatibility,
                "external_source_ref_count": len(external_source_refs),
                "test_ref_count": len(test_refs),
                "signal_ref_count": len(signal_refs),
                "references": refs,
            }
        )

    metrics = {
        "workbench_lines": len(text.splitlines()),
        "widget_method_count": len(method_rows),
        "thin_method_count_le_4": sum(row["size"] <= 4 for row in method_rows),
        "connection_count": len(connections),
        "test_count": len(tests),
        "tests_with_private_refs": sum(bool(row["private_refs"]) for row in tests),
        "private_test_ref_occurrences": sum(row["private_ref_count"] for row in tests),
        "unique_private_test_refs": len(private_counter),
    }
    return {
        "source": WORKBENCH_PATH.relative_to(ROOT).as_posix(),
        "metrics": metrics,
        "workflow_method_counts": dict(Counter(row["workflow"] for row in method_rows)),
        "compatibility_counts": dict(Counter(row["compatibility"] for row in method_rows)),
        "methods": method_rows,
        "connections": connections,
        "tests": tests,
        "private_test_references": dict(private_counter.most_common()),
    }


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |" for row in rows)
    return output


def render_markdown(report: dict[str, object]) -> str:
    metrics = report["metrics"]
    lines = ["# TIF Workbench Architecture Baseline", "", "## Metrics", ""]
    lines.extend(_markdown_table(["Metric", "Value"], [[key, value] for key, value in metrics.items()]))
    lines.extend(["", "## Workflow Method Counts", ""])
    lines.extend(_markdown_table(["Workflow", "Methods"], sorted(report["workflow_method_counts"].items())))
    lines.extend(["", "## Compatibility Counts", ""])
    lines.extend(_markdown_table(["Class", "Methods"], sorted(report["compatibility_counts"].items())))
    lines.extend(["", "## Methods", ""])
    lines.extend(
        _markdown_table(
            ["Line", "Size", "Method", "Workflow", "Compatibility", "Source refs", "Test refs", "Signal refs"],
            [
                [row["line"], row["size"], f"`{row['name']}`", row["workflow"], row["compatibility"], row["external_source_ref_count"], row["test_ref_count"], row["signal_ref_count"]]
                for row in report["methods"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def render_test_migration_markdown(report: dict[str, object]) -> str:
    lines = [
        "# TIF Workbench Round 3 Test Migration Ledger",
        "",
        "由 `scripts/analyze_tif_workbench_architecture.py` 生成。`target_layer` 是 Stage 0 初始建议，实施阶段必须结合测试真实断言复核。",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["File", "Line", "Test", "Workflow", "Private refs", "Initial target"],
            [
                [
                    row["file"],
                    row["line"],
                    f"`{row['test']}`",
                    row["workflow"],
                    ", ".join(f"`{name}`" for name in row["private_refs"]) or "-",
                    row["target_layer"],
                ]
                for row in report["tests"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def render_signal_migration_markdown(report: dict[str, object]) -> str:
    lines = [
        "# TIF Workbench Round 3 Signal Migration Ledger",
        "",
        "由 `scripts/analyze_tif_workbench_architecture.py` 生成。目标 controller 和迁移阶段在各 Stage 实施时填写并复核。",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["Line", "Signal", "Current target", "Workflow", "Target owner", "Stage", "Contract test"],
            [
                [
                    row["line"],
                    f"`{row['signal']}`",
                    f"`{row['target']}`" if row["target"] else "-",
                    row["workflow"],
                    "TBD",
                    "TBD",
                    "TBD",
                ]
                for row in report["connections"]
            ],
        )
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit TifWorkbenchWidget architecture coupling.")
    parser.add_argument("--json", type=Path, help="Write full machine-readable report.")
    parser.add_argument("--markdown", type=Path, help="Write method inventory Markdown.")
    parser.add_argument("--test-ledger", type=Path, help="Write test migration ledger Markdown.")
    parser.add_argument("--signal-ledger", type=Path, help="Write signal migration ledger Markdown.")
    parser.add_argument("--summary", action="store_true", help="Print summary JSON.")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    if args.test_ledger:
        args.test_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.test_ledger.write_text(render_test_migration_markdown(report), encoding="utf-8")
    if args.signal_ledger:
        args.signal_ledger.parent.mkdir(parents=True, exist_ok=True)
        args.signal_ledger.write_text(render_signal_migration_markdown(report), encoding="utf-8")
    if args.summary or not any((args.json, args.markdown, args.test_ledger, args.signal_ledger)):
        print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
