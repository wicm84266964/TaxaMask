---
name: paper-distill
description: Distill one markdown paper into structured QA records by wrapping the existing standalone paper-distill CLI.
allowed-tools: powershell, read_file, list_files, glob, document_intake
version: 0.2.0
---

# Paper Distill Skill

## Purpose

Use this skill when a coding agent needs to distill a single markdown paper into structured question-answer training data, reusable paper knowledge maps, or conversation-style training records without reimplementing the `paper_distill` subsystem.

This bundle is intentionally host-agnostic. It teaches a host how to invoke the already-existing command surface instead of embedding host-specific tool schemas.

All distillation outputs should be written in Chinese, even when the source paper is in English, because the downstream training target is a Chinese-base model.

## When to use

- The user wants to distill one markdown paper into training QA pairs.
- The user wants to export one paper into one or more conversation-oriented training records.
- The user wants to resume or restart a paper-specific distillation run.
- The user wants to export merged paper-distill outputs to `json` or `jsonl`.
- The user wants English-language papers to be distilled into Chinese training data.

## When not to use

- The request is about the main task runtime or web console.
- The input is not a markdown paper file.
- The user wants multi-paper orchestration beyond the existing `paper-distill` command surface.

## Stable entrypoints

Bundle root is the directory that contains this repository-local package:

```text
skills/paper_distill_skill_bundle_v6_zh
```

Prefer the installed script when available:

```powershell
paper-distill --help
```

Fallback to the module entrypoint when the installed script is unavailable:

```powershell
$root = Join-Path (Get-Location) "skills/paper_distill_skill_bundle_v6_zh"
$oldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($oldPythonPath) { "$root;$oldPythonPath" } else { $root }
Push-Location $root
try {
  python -m app.paper_distill --help
} finally {
  Pop-Location
  $env:PYTHONPATH = $oldPythonPath
}
```

Ant Code may start from an arbitrary project cwd. When using the fallback module entrypoint, always use the wrapper above so local package imports resolve. Keep user paper paths, workspace roots, artifact roots, and output paths explicit.

## Inputs

Required for `run`:

- `--paper <path>`
- exactly one of `--target-count <int>` or `--auto-target-count`

Optional for `run`:

- `--min-target-count <int>`
- `--max-target-count <int>`
- `--batch-size <int>`
- `--workspace-root <path>`
- `--artifacts-root <path>`
- `--cache-root <path>`
- `--backend mock|openai-compatible`
- `--model <name>`
- `--base-url <url>`
- `--api-key <secret>`
- `--timeout-seconds <float>`
- `--temperature <float>`
- `--restart`

Required for `export`:

- exactly one of `--artifact-dir <path>` or `--artifacts-root <path>`
- `--format json|jsonl|conversation-jsonl`
- `--output <path>`

## Default locations

- artifacts root: `data/paper_distill/papers`
- cache root: `data/paper_distill/cache`

When `--workspace-root` is omitted, these relative defaults resolve under `AGENT_WORKSPACE_ROOT` if it is set; otherwise they resolve under the current working directory.

Per-paper artifacts are written under:

```text
data/paper_distill/papers/<paper_id>/
  qa_entries.jsonl
  conversation_entries.jsonl
  checkpoint.json
  knowledge_map.json
  conversation_plan.json
```

## Canonical commands

Run or resume distillation for one markdown paper:

```powershell
paper-distill run --paper papers/example.md --target-count 30 --batch-size 3 --backend mock
```

Run with automatic target sizing based on paper length, structure, and extracted paper signals:

```powershell
paper-distill run --paper papers/example.md --auto-target-count --min-target-count 8 --max-target-count 24 --batch-size 2 --backend mock
```

Export merged QA records from one artifacts root:

```powershell
paper-distill export --artifacts-root data/paper_distill/papers --format jsonl --output data/paper_distill/export.jsonl
```

Export one paper as one or more conversation records:

```powershell
paper-distill export --artifact-dir data/paper_distill/papers/<paper_id> --format conversation-jsonl --output data/paper_distill/conversation.jsonl
```

If `paper-distill` is not installed, run the same subcommands through:

```powershell
python -m app.paper_distill <subcommand> <args>
```

using the `Bundle root` wrapper from the stable entrypoints section.

## Success signals

`run` prints line-oriented status values such as:

- `paper_id=...`
- `artifact_dir=...`
- `target_count=...`
- `accepted_count=...`
- `entries_written=...`
- `cache_status=...`
- `status=completed|in_progress`

`export` prints:

- `output=...`
- `format=json|jsonl|conversation-jsonl`
- `record_count=...`

Treat the on-disk artifacts as the source of truth:

- `qa_entries.jsonl`
- `conversation_entries.jsonl`
- `checkpoint.json`
- `knowledge_map.json`
- `conversation_plan.json`
- exported `json` / `jsonl`

## Environment variables

Optional environment variables already supported by the CLI:

- `PAPER_DISTILL_BACKEND`
- `PAPER_DISTILL_MODEL`
- `PAPER_DISTILL_BASE_URL`
- `PAPER_DISTILL_API_KEY`

## Host adaptation notes

- Wrap the existing `paper-distill` CLI or `python -m app.paper_distill` entrypoint.
- Do not reimplement `app.paper_distill` internals in the host adapter.
- Keep host-specific tool schemas, slash commands, or permission models outside this bundle.
- If the host needs machine-native status parsing, read the generated artifact files in addition to stdout.
- When configuring prompts or adapters around this bundle, keep the generated knowledge maps, plans, questions, answers, and conversation records in Chinese.

## Non-goals

- This skill does not register a new host-specific runtime tool.
- This skill does not integrate with the main task runtime or web console.
- This skill does not alter prompt versions, artifact schema, or backend behavior.

## Reference

Operational details remain in the repository README under `## Paper distill`.
