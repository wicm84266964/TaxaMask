# Ant Code RC Acceptance Summary

This document is the human-readable acceptance summary for an Ant Code release candidate. The accepted v1.0 internal release is recorded in `docs/deployment/v1.0-acceptance.md`.

## Candidate Scope

The candidate provides:

- local CLI entrypoints through `ant-code`
- local file, git, shell, workflow, memory, and MCP boundaries
- local permission checks for writes and mutating commands
- model gateway/model adapter support for provider-independent model traffic
- no MVP dependency on remote tool servers
- local session metadata controls, including high-sensitivity zero-retention mode
- clean-room provenance and release seal evidence

## Acceptance Criteria

The candidate is acceptable for controlled lab rollout when:

- `npm run verify:release` passes from a clean working tree
- `npm run check:release-seal` passes
- `npm run verify:install` passes
- `ant-code doctor` has no unexpected errors on target lab machines
- `node scripts/verify-gateway-compat.js --live --json` passes against the chosen model adapter before broad model-enabled use
- high-sensitivity projects use zero-retention or approved encrypted local metadata
- lab operators have documented gateway/model adapter quota, retention, and rollback policy

## Current Non-Goals

The candidate does not include:

- remote tool execution
- cloud remote sessions
- public plugin marketplace access
- direct provider credentials in the local client
- transcript upload
- public package publishing

## First Cohort Recommendation

Start with a small internal cohort using:

- one lab-managed model adapter endpoint
- one approved model alias
- high-sensitivity mode for private research projects
- local-only tools and explicit write/command approvals
- mandatory `/report` output before handing off changed code

## Rollback Summary

Disable model turns by unsetting `LAB_MODEL_GATEWAY_URL` and `LAB_MODEL_GATEWAY_HEALTH_URL`, then set `LAB_AGENT_NETWORK_MODE=offline`. Local slash commands, diagnostics, and cleanup remain available without model access.
