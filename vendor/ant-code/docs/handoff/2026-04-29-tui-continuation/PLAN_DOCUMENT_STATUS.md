# Plan Document Status

Date: 2026-04-29

This file maps the copied planning/specification documents to current implementation status.

The copied source documents live under:

```text
docs/handoff/2026-04-29-tui-continuation/plan-documents/docs/
```

Status meanings:

- Done: implemented enough for the current internal build and covered by `npm run check` or release docs.
- Partial: meaningful implementation exists, but live UX validation or additional polish remains.
- Pending: planned but not implemented or not release-ready.
- Reference: policy/background document; not a feature checklist by itself.

## Executive Summary

The clean-room MVP foundation is mostly implemented: local CLI/runtime, model gateway, local tools, permissions, context compaction, event stream, TUI baseline, model selection, session metadata, audit checks, and internal release documentation all exist.

The main remaining area is advanced product depth rather than core TUI usability. The latest continuation tightened `/guide` and interrupt shortcut copy so the documented behavior matches the current checkpoint-interrupt-and-run-next implementation, changed busy `Esc` to a two-press interrupt confirmation while keeping `Ctrl+G` as direct interrupt, made common visible TUI and slash-command discovery copy Chinese-first for lab users, changed context display to token-first with configured model windows, upgraded `/compact` to prefer model summarization through the lab gateway with local fallback, fixed raw-terminal `Ctrl+O` detail toggling, clarified `/help` as a read-only documentation panel, made command-panel row counters understandable, changed default transcript scrolling to the TUI-owned viewport so the right side panel can stay pinned, fixed Backspace/Delete handling in the live composer, and closed Stage 7 for controlled internal delivery. On 2026-04-29 the user manually accepted Stage 4 through Stage 6 in the real TUI, then confirmed sessions/resume, `/guide`, and `/compact` were usable; queue/file-mention/shortcut edge cases are covered by automated tests and explicit non-blocking release decisions.

## Copied Planning Documents

| Copied document | Status | Done | Not done / next |
| --- | --- | --- | --- |
| `plan-documents/docs/phase-0/README.md` | Done | Phase 0 audit package exists and clean-room risk posture was used to start the new repo. | Keep as historical evidence; update only if new contamination risk is discovered. |
| `plan-documents/docs/phase-0/old-repo-audit-register.md` | Done | Old-repo audit register exists for risk tracking. | Do not use polluted source as implementation input; reviewer-only behavior specs remain the boundary. |
| `plan-documents/docs/phase-1/README.md` | Done | New repository setup and initial clean-room project framing were completed. | Historical only unless repository bootstrap changes. |
| `plan-documents/docs/architecture/repository-blueprint.md` | Done | Repository layout, docs layout, source module split, and test structure are in place. | Keep aligned if modules are renamed or packaging changes. |
| `plan-documents/docs/architecture/mvp-architecture.md` | Partial | Core runtime, local tools, model gateway, MCP stdio, permissions, context, workflow state, TUI, and audit flows exist. | Advanced editor panes, final TUI polish, and some richer workflow surfaces remain incomplete. |
| `plan-documents/docs/branding/public-identity.md` | Done | External identity is Ant Code; internal package still uses lab-agent-compatible structure where useful. | Revisit before public-facing distribution or publication. |
| `plan-documents/docs/cloud/cloud-capability-inventory.md` | Done | Cloud-only capabilities were inventoried and excluded from the local MVP. | Revisit only if lab later asks for remote/cloud features. |
| `plan-documents/docs/cloud/cloud-capability-gap-analysis.md` | Done | Local-first replacement strategy is documented; no remote tool servers are required. | Lab-owned optional replacements remain future work. |
| `plan-documents/docs/security/data-boundary.md` | Partial | Local tool execution boundary, gateway-owned provider credentials, transcript/context controls, and secret redaction exist. | Continue manual validation for high-sensitivity lab use and release packaging. |
| `plan-documents/docs/provenance/clean-room-provenance-policy.md` | Done | Provenance checks exist and pass; clean-room policy is documented. | Keep updating module provenance notes when new modules are added. |
| `plan-documents/docs/specs/mvp-product-spec.md` | Partial | CLI, print mode, local tools, permissions, model gateway, context, slash commands, workflow state, and TUI baseline exist. | Some product polish and advanced TUI/editor workflows remain incomplete. |
| `plan-documents/docs/specs/tool-and-permission-spec.md` | Partial | Read/write/shell/tool permission policy exists with approvals and tests. | Productized Plan/Build mode framing and final permission UX polish remain open. |
| `plan-documents/docs/specs/lab-model-gateway-protocol.md` | Done | Gateway protocol and OpenAI-compatible adapter support exist with tests. | Real lab gateway smoke testing should continue whenever gateway behavior changes. |
| `plan-documents/docs/specs/lab-model-gateway-compatibility-matrix.md` | Partial | Compatibility docs and tests cover configured local gateway style. | Keep matrix current against the user's real gateway and model aliases. |
| `plan-documents/docs/specs/tui-experience-parity-design.md` | Partial | Stage A-F style foundation exists and Stage 4-6-equivalent live TUI flows were accepted by the user on 2026-04-29: streaming transcript/detail, tool permission UX, and command product panels. | Stage G advanced workflows and Stage H hardening are incomplete; final release docs/evidence still need refresh. |
| `plan-documents/docs/specs/experience-parity-v1.1.md` | Partial | v1.1 baseline items landed: streaming, tool status, startup identity, model selector, resize fixes, sky-blue direction; current Stage 4-6 TUI experience was manually accepted. | v1.2 polish continues mainly around Stage 7-9 scope and release hardening. |
| `plan-documents/docs/specs/tui-v1.2-interaction-polish-outline.md` | Partial | Stages 1-7 are accepted for the current internal build. Latest work added TUI-owned transcript scrolling, `/guide`, token-first context/window display, shortcut feedback, clearer `/guide` copy, Chinese-first common UI/discovery copy, deterministic scroll coverage, Backspace/Delete raw-input handling, model-summary-first `/compact`, and package file whitelisting. | Stage 8 local extension depth remains partial/non-blocking; Stage 9 is in final verification/package-hash freeze. |
| `plan-documents/docs/deployment/local-installation.md` | Done | Local launch and install commands exist; user currently launches with `node .\src\cli\index.js tui`. | Update if the final recommended launch command changes. |
| `plan-documents/docs/deployment/model-adapter-gateway-readiness.md` | Partial | Local gateway configuration path exists; OpenAI-compatible gateway support exists. | Keep validating against the user's real `localhost:8080` gateway; do not persist secrets in repo files. |
| `plan-documents/docs/deployment/pre-launch-security-config.md` | Partial | Security config docs exist and checks pass. | Needs final lab-specific review before broad internal rollout. |
| `plan-documents/docs/deployment/lab-gateway-rollout-checklist.md` | Partial | Rollout checklist exists. | Real lab rollout remains pending until TUI manual validation and gateway smoke tests pass. |
| `plan-documents/docs/deployment/release-candidate-package.md` | Partial | RC packaging docs and generated audit flow exist. | Refresh after final TUI polish and validation. |
| `plan-documents/docs/deployment/rc-acceptance-summary.md` | Partial | RC acceptance summary exists. | Update after current TUI continuation tasks are validated. |
| `plan-documents/docs/deployment/v1.0-acceptance.md` | Done | v1.0 acceptance was recorded for the earlier internal release posture. | Historical baseline; newer TUI polish should be recorded separately. |
| `plan-documents/docs/deployment/v1.1-experience-acceptance.md` | Partial | v1.1 experience pass was recorded. | Needs follow-up for v1.2/current polish once user validates small-window scroll, `/guide`, and shortcut audit. |

## TUI Stage Status From Current Plans

### Original TUI Experience Parity Design

| Stage | Status | Notes |
| --- | --- | --- |
| Stage A: Design And Test Harness | Done | Terminal snapshot helpers and unit-level format tests exist. |
| Stage B: Event Model V2 | Done | AntEvent v2 normalization/reducer tests exist and pass. |
| Stage C: Transcript-First Shell | Done | Transcript-first TUI exists; default scrolling is TUI-owned, context status is token-first, and the user accepted long streaming/detail/scroll behavior in the real TUI. |
| Stage D: Composer And Palettes | Done | Multi-line composer, cursor handling, slash palette, and file mention palette exist. |
| Stage E: Tool And Permission UX | Done/Polish | Tool cards and permission modals exist; the user accepted a live self-create/write/read file permission flow. Further work is visual polish, not core acceptance. |
| Stage F: Session And Product Commands | Done/Polish | `/model`, `/queue`, `/compact`, `/sessions`, `/resume`, `/clear`, `/status`, `/help`, usage/cost, and panels exist; `/compact` now prefers model summarization through the lab gateway with local fallback; common discovery/panel copy is Chinese-first; `/resume` accepts unique id prefixes and restores bounded retained transcript messages when available. Stage 6 command panels were accepted in live TUI. Some advanced commands remain intentionally disabled/stubbed. |
| Stage G: Advanced Workflows | Partial/Deferred | Queue exists and is tested; richer branch/stash/background/task dashboard and plan approval are deferred as non-blocking Stage 8 depth. |
| Stage H: Release Hardening | Delivery | `npm run check` and release verification pass; final live TUI acceptance is recorded and package hashing is recorded outside the package before distribution. |

### v1.2 Interaction Polish Outline

| Stage | Status | Notes |
| --- | --- | --- |
| Stage 1: Renderer Contract And Theme Tokens | Done | Sky-blue theme and theme tokens exist. |
| Stage 2: Composer/Input v2 | Done | Cursor-aware input and wide-character tests exist. |
| Stage 3: Popovers And Interrupt Semantics | Done | Popover priority exists; busy `Esc` requires a second press to interrupt, `Ctrl+G` directly interrupts, and prior live testing confirmed the new interrupt behavior. |
| Stage 4: Transcript Blocks And Streaming Rhythm | Done/Polish | Live states and transcript blocks exist; token-based context/window status is visible; the user accepted long streaming scroll, right-panel stability, and `Ctrl+O` detail expansion in the real TUI. |
| Stage 5: Tool Cards And Permission Modals | Done/Polish | Tool cards and permission modal frames exist; the user accepted a live self-create/write/read file workflow with an operable permission confirmation box. |
| Stage 6: Command Product Surfaces | Done/Polish | Product panels exist for key commands; disabled local replacements are documented in Chinese-first user-facing copy; the user accepted `/help`, `/status`, `/model`, `/context`, `/usage`, `/cost`, `/permissions`, `/gateway`, and `/keybindings` style command surfaces. |
| Stage 7: File, Session, And Queue Workflows | Done/Delivery | Queue, sessions, file mentions, latest `/guide` checkpoint behavior, model-summary `/compact`, visible `Ctrl+O` detail folding, and metadata resume summaries exist. The user confirmed current session/resume behavior, `/guide`, and `/compact`; queue/file-mention/shortcut edge cases are covered by automated tests and accepted as non-blocking for the internal handoff. |
| Stage 8: Agent, MCP, And Local Extension Panels | Partial | MCP and agents command surfaces exist; richer TUI panels are not product-complete. |
| Stage 9: Release Hardening | Delivery | Automated hardening passed on 2026-04-29: `npm run check` passed with 241 tests after the model-summary `/compact` upgrade, `npm run verify:release` passed, generated audit/release summaries were refreshed, final Stage 7 release status is recorded, live gateway evidence is deferred to the lab operator, and package hash recording is handled outside the package. |

## Current Highest-Priority Continuation Items

1. Run the final verification commands and attach the external package SHA256 evidence.
2. Keep Stage 8 as partial/non-blocking: current MCP and readonly agents are functional, while skills/richer extension panels remain deferred.
3. Lab operators should attach live gateway compatibility evidence before broad model-enabled rollout.
4. Keep OpenCode-like sky-blue polish as future product depth: stream rhythm, tool cards, status/context meter, compact layouts, and command panels can improve further without blocking the current internal acceptance.
