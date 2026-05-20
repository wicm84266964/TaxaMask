# Clean-room Provenance Policy

本文档定义实验室新代码助手主仓库的来源边界、协作方式和审计要求。

## Goal

新主仓库的目标是从零实现一个实验室自研本地代码智能体。它可以兼容公开协议和公开产品行为，但不能继承旧仓库中的非公开源码、实现结构、注释、类型命名或私有云端协议细节。

## Current Repository Status

当前旧仓库被归类为污染参考实现。

理由：

- 项目文档明确记录旧仓库基于 2026-03-31 流出的 Claude Code 源码改造。
- 源码中大量保留 `Claude`、`Anthropic`、`claude.ai`、`growthbook`、`statsig`、`datadog`、`sourceMappingURL=data` 等来源指纹。
- 仓库缺少 `.git` 历史，无法建立完整提交来源链。
- 仓库缺少根级许可证和 NOTICE 文件，无法证明完整分发许可。

## Allowed Inputs

新仓库可以参考以下来源：

| Source type | Allowed use |
| --- | --- |
| Official public documentation | Feature behavior, public API shapes, public configuration semantics |
| Public SDKs and packages | Normal dependency usage according to their licenses |
| Public standards | JSON-RPC, MCP, POSIX shell behavior, PowerShell behavior, Git behavior |
| Experiment-lab specifications | Requirements, security policy, deployment policy, UX expectations |
| Black-box behavior observations | User-visible behavior descriptions, without copying implementation |
| Public issue discussions and examples | High-level behavior and edge cases, with citation |

Recommended public reference set:

- Claude Code overview: `https://docs.anthropic.com/en/docs/claude-code/overview`
- Claude Code settings: `https://docs.anthropic.com/en/docs/claude-code/settings`
- Claude Code memory: `https://docs.anthropic.com/en/docs/claude-code/memory`
- Claude Code slash commands: `https://docs.anthropic.com/en/docs/claude-code/slash-commands`
- Claude Code subagents: `https://docs.anthropic.com/en/docs/claude-code/sub-agents`
- Claude Code MCP: `https://docs.anthropic.com/en/docs/claude-code/mcp`
- Anthropic Messages API: `https://docs.anthropic.com/en/api/messages`
- Model Context Protocol: `https://modelcontextprotocol.io/`

## Prohibited Inputs

The new repository must not use:

- Code copied from the old repository.
- Decompiled or reconstructed implementation details from old inline source maps.
- Old file layouts as an implementation template.
- Old private endpoint schemas not documented publicly.
- Old UI component structure or state machine structure.
- Old test snapshots, fixtures, or golden transcripts.
- Old comments, docstrings, and internal bug references.
- Private Anthropic / Claude.ai feature flag names as new implementation concepts.

## Team Roles

Use two roles whenever staffing allows.

| Role | Responsibility | Old repository access |
| --- | --- | --- |
| Spec writer | Convert needs into public-doc-based behavior specs and migration tests | Allowed, but must not copy code |
| Implementer | Write new code from specs and public docs | Should not inspect old source |
| Reviewer | Check provenance, security boundary, and behavior | May inspect both, but must flag contamination risk |

If staffing does not allow strict separation, each contributor must record any old-source exposure in the module provenance note.

## Module Provenance Requirement

Each new module must include a nearby provenance record before it is merged.

Minimum fields:

```yaml
module: src/tools/read-file
owner: lab-tooling
implementation_status: clean-room
implementer_old_source_exposure: none | limited | known
references:
  - public_doc: https://...
  - standard: POSIX shell / JSON-RPC / MCP
design_notes:
  - Short summary of independent design choices.
prohibited_sources_checked:
  - old source code was not copied
  - old inline source maps were not used
```

For a small module, this can live in `docs/provenance/modules/<module>.md`. For larger subsystems, keep one record per subsystem and link to design docs.

## Naming Rules

Use lab-owned names, not upstream product names, except when referring to public protocol names or model IDs.

Avoid:

- `ClaudeCode*`
- `Tengu*`
- `CCR*`
- `Grove*`
- `GrowthBook*`
- `Statsig*`
- `Datadog*`
- `claude.ai*`

Prefer:

- `LabAgent`
- `SessionRuntime`
- `ToolRuntime`
- `PolicyEngine`
- `LabModelGateway`
- `LabPluginRegistry`
- `LocalMemory`

## New Repository Baseline

Recommended initial tree:

```text
docs/
  provenance/
  specs/
  security/
src/
  core/
  model-gateway/
  tools/
  permissions/
  mcp/
  memory/
  commands/
  agents/
  ui/
  storage/
  config/
```

Do not mirror the old `src/bridge`, `src/services/api`, `src/services/analytics`, `src/components`, or `src/utils` split.

## Review Gate

Before a module is merged, reviewers must answer:

- Is the behavior described by a public document, public standard, or lab-owned requirement?
- Is the implementation structurally independent from the old repository?
- Does the module avoid private Claude.ai endpoints and feature flags?
- Does the module keep research data inside the approved data boundary?
- Does the module have tests written from behavior requirements, not old fixtures?

## Immediate Actions

- Freeze old repository access to maintainers and spec writers.
- Remove old repository from onboarding materials.
- Build new repository from an empty initial commit.
- Create `docs/provenance/modules/` in the new repository.
- Require provenance notes in pull requests.
- Treat old repository references as audit evidence, not source material.
