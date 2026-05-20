---
module: src/dashboard
owner: lab-tooling
implementation_status: clean-room
implementer_old_source_exposure: limited-audit-context
references:
  - lab_plan: docs/plans/active/dashboard-webui-plan-2026-05-13.md
  - lab_spec: docs/specs/mvp-product-spec.md
  - lab_spec: docs/specs/tool-and-permission-spec.md
design_notes:
  - Adds the local-only `ant-code dashboard` WebUI adapter without changing the existing TUI implementation.
  - Reuses the existing core session runtime, local tool permission engine, and `.lab-agent/sessions` store instead of creating a separate task history.
  - Exposes a loopback HTTP server bound to `127.0.0.1` by default and rejects non-loopback host binding in the first release.
  - Converts core session events into folded dashboard activities so tool execution remains traceable but quiet by default.
  - Implements a web approval bridge for allow-once, allow-session, deny, and cancel decisions while keeping tool execution behind the existing local approval callback.
  - Provides an explicit WebUI shutdown action that stops the local dashboard server instead of leaving a silent background process.
  - Provides a dark gray, Codex-inspired, three-panel frontend for threads, conversation/activity flow, and file previews.
  - File preview is bounded to the current workspace, limits large reads, and does not execute or edit files from the preview surface.
prohibited_sources_checked:
  - old source code was not copied
  - old inline source maps were not used
  - Codex product behavior was used only as visible interaction inspiration; no private implementation details were used
---

# Dashboard Provenance

The Dashboard module is a fresh WebUI adapter for Ant Code. It is derived from
the lab-approved Dashboard plan and existing local Ant Code interfaces, not from
legacy source internals.
