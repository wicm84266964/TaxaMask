# Repository Instructions

## User collaboration preferences
- The user is an ant taxonomy researcher, not a deeply algorithm-focused engineer.
- When explaining code, debugging behavior, or discussing implementation plans, explain in plain language first.
- Prefer concrete workflow explanations over abstract software jargon.
- When discussing technical changes, connect them to what they mean for real research tasks (for example: PDF screening, candidate review, annotation, training, or result trustworthiness).
- Default to Chinese when explaining work to the user unless the user explicitly asks for English.
- When presenting risks or options, clearly distinguish:
  - what the program is doing
  - why it matters for the user's workflow
  - what tradeoff or operational consequence it creates

## Project origin and strategic background
- `AntSleap` is intentionally named as a tribute to the `SLEAP` project that originally inspired the user.
- The project was originally created to solve real ant taxonomy workflow needs, so ant-centered assumptions are historically grounded rather than accidental.
- Current stance: prioritize a stable landing in the ant domain first; treat support for other taxa as a later possibility, not the default product claim.

## Root documentation rules
- Root-level long-term documentation is intentionally reduced to two maintained files:
  - `CHANGELOG_zh.md`
  - `LLM_CONTEXT_DETAILED.md`
- Do **not** recreate the older four-document root set (`README.md`, `README_zh.md`, `LLM_CONTEXT.md`, `LLM_CONTEXT_DETAILED.md`) unless the user explicitly asks.
- Do **not** update these two Markdown files after every small code change by default.
- Default workflow: leave them untouched during normal intermediate edits, and sync them only when one of the following is true:
  - the user explicitly asks for documentation/context synchronization
  - the user is doing an end-of-day or end-of-session summary pass
  - the current code change is so significant that leaving the docs unsynced would create misleading or unsafe operating guidance
- `CHANGELOG_zh.md` is the single Chinese historical changelog-style document:
  - append new updates under the appropriate date entry
  - do not rewrite or retroactively alter older dated logs unless the user explicitly requests a historical correction
- `LLM_CONTEXT_DETAILED.md` is the current-state handoff/context document:
  - update them so they reflect the latest actual program state
  - prefer synchronizing them to the current architecture/behavior rather than writing them as historical changelogs
- In other words: these two files are maintained on a deliberate summary cadence, not as mandatory companions to every code patch.

## Change communication habits
- After meaningful code changes, explain the result in a way a domain researcher can follow.
- When changing output structure, runtime behavior, or validation logic, explicitly tell the user:
  - where files will appear
  - what each artifact is for
  - what changed compared with the previous behavior
- For parameter tuning or algorithm choices, explain not just the value, but why it is a practical default.
- Prefer stable, auditable, recovery-friendly solutions over clever but opaque designs.
- If a change affects large-scale runs or data safety, call that out directly.

## Local Git workflow
- Treat Git as a local, offline version history unless the user explicitly asks to connect or push to GitHub.
- Do not add a remote repository, run `git push`, or publish code unless the user clearly requests it.
- Prefer committing after the user accepts a coherent milestone, not after every tiny edit.
- Before committing, run `git status --short` and review the staged file list so local data, API keys, databases, model weights, and run outputs are not accidentally included.
- Keep `.gitignore` conservative for research safety:
  - exclude user runtime config, API settings, local project JSON files, databases, model weights, and generated artifacts by default
  - include only intentional templates, source code, tests, maintained documentation, and small reproducible configuration examples
- Use clear Chinese or concise English commit messages that describe the research workflow change, for example: `标注工作台部位树与 Blink 路由联动`.
- Never use destructive Git commands such as `git reset --hard`, `git clean -fd`, or checkout-based rollback unless the user explicitly asks for that operation.

## Temporary validation artifacts
- Do not create root-level temporary folders like `tmp_*` for ad hoc validation or smoke tests.
- Use `.tmp_validation/` for disposable local test artifacts created by coding agents.
- Clean up temporary validation artifacts before finishing, unless the user explicitly asks to keep them.
- Keep validation output out of normal project directories unless the artifact is a real project deliverable.

## Output hygiene
- Prefer run-scoped or feature-scoped output directories already used by the codebase.
- Do not leave one-off debug files in the repository root.
