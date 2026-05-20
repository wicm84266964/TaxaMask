# Phase 0 Audit Deliverables

本目录记录 Ant Code clean-room 新主仓库启动前的第 0 阶段审计结论。

## Scope

审计对象是当前旧仓库：

- `C:\saveproject\LBJ-workspace\ant-code-latest`

第 0 阶段目标不是继续修补旧实现，而是给新主仓库建立清楚边界：

- 哪些能力可以基于公开文档和实验室自研设计重做。
- 哪些能力属于 Claude / Anthropic 云端私有服务，不能直接继承。
- 哪些旧仓库内容属于污染参考，只能用于高层行为描述，不能复制代码。
- 科研数据在新系统中的默认流向和禁止流向。

## Deliverables

- [Old Repository Audit Register](old-repo-audit-register.md)
- [Clean-room Provenance Policy](../provenance/clean-room-provenance-policy.md)
- [Claude Cloud Capability Inventory](../cloud/cloud-capability-inventory.md)
- [Claude Cloud Capability Gap Analysis](../cloud/cloud-capability-gap-analysis.md)
- [Research Data Boundary](../security/data-boundary.md)
- [Phase 1 Design Package](../phase-1/README.md)

## Audit Snapshot

旧仓库明确记录其工程起点来自 2026-03-31 流出的 Claude Code 源码：

- `LLM_HANDOFF.md` 写明项目用途为“基于 2026-03-31 流出的 Claude Code 源码改造”。
- `CHANGELOG.md` 写明 `1.0.0` 是“以 Claude Code 源码为起点”。
- 当前工作区没有 `.git` 元数据，无法用提交历史建立完整来源链。
- 根目录没有 `LICENSE` / `NOTICE` / `COPYING` 文件。

源码规模和来源指纹：

| Audit item | Result |
| --- | ---: |
| TS/JS source files under `src` | 1,934 |
| TS/JS source lines under `src` | 483,891 |
| Files containing `Claude` | 770 |
| Files containing `Anthropic` | 322 |
| Files containing `Claude Code` | 110 |
| Files containing inline `sourceMappingURL=data:application/json` | 547 |
| Files containing `growthbook` | 177 |
| Files containing `statsig` | 38 |
| Files containing `datadog` | 23 |

High-density cloud / external-service areas:

| Area | Files | Lines | Notes |
| --- | ---: | ---: | --- |
| `src/utils/plugins` | 44 | 18,858 | marketplace, plugin cache, official source handling |
| `src/bridge` | 31 | 11,761 | remote control, bridge sessions, OAuth-backed polling |
| `src/services/mcp` | 23 | 11,348 | local MCP plus Claude.ai managed MCP and official registry |
| `src/services/api` | 20 | 9,662 | model API, files API, metrics, Grove, session ingress |
| `src/services/analytics` | 9 | 3,680 | GrowthBook, Datadog, first-party event logging |
| `src/services/teamMemorySync` | 5 | 2,024 | cloud team memory sync |
| `src/services/remoteManagedSettings` | 5 | 860 | cloud-managed org settings |
| `src/services/settingsSync` | 2 | 589 | user settings cloud sync |
| `src/services/policyLimits` | 2 | 614 | org policy limits from API |

Endpoint / cloud-reference scan:

| Pattern | Files | Matches |
| --- | ---: | ---: |
| `/v1/sessions` | 12 | 41 |
| `https://claude.ai` | 17 | 33 |
| `/v1/code` | 16 | 28 |
| `/api/claude_code` | 12 | 16 |
| `https://api.anthropic.com` | 11 | 15 |
| `https://platform.claude.com` | 7 | 12 |
| `/v1/files` | 2 | 5 |
| `/v1/mcp_servers` | 2 | 2 |
| `mcp-proxy.anthropic.com` | 1 | 1 |
| `http-intake.logs.us5.datadoghq.com` | 1 | 1 |

## Phase 0 Decision

旧仓库应冻结为污染参考实现。它可以用于：

- 描述用户可见行为。
- 记录旧系统的风险入口。
- 设计迁移验收测试。
- 比较新系统缺失的能力。

它不能用于：

- 复制代码、类型、注释、文件结构、测试 fixture。
- 直接迁移云端协议实现。
- 直接迁移 UI 组件结构。
- 作为新仓库的长期主干。

新主仓库应从空仓库开始，基于公开文档、公开 SDK、标准协议和实验室自研设计实现。
