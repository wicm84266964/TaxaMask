# ant-code-latest Reference Status

This handoff continues work in:

```text
C:\saveproject\LBJ-workspace\lab-agent
```

There is also a sibling/local workspace path:

```text
C:\saveproject\LBJ-workspace\ant-code-latest
```

## Current Meaning

`ant-code-latest` is the primary product/reference baseline for this rebuild.

The clean-room `lab-agent` repository is being built to replace and preserve the important capabilities, workflows, and interaction quality of that existing Ant Code project. In other words:

- `ant-code-latest` is the main reference for what the user expects Ant Code to feel like and be able to do.
- `lab-agent` is the new clean-room implementation repository.
- The rebuild is based on behavior, product requirements, logs, audits, and sanitized specifications derived from the existing project.
- The rebuild is not based on direct source copying from `ant-code-latest`.

Treat `ant-code-latest` as a reference/baseline project, not as the place where new code should be implemented.

## Why This Matters

There are two separate roles:

1. Reference role: `ant-code-latest` is the existing Ant Code project whose behavior and user experience motivate the rebuild.
2. Implementation role: `lab-agent` is the clean-room repository where new implementation work happens.

The user previously noticed that a global `ant-code` command could start a different installation than the clean-room repo. That can make tests look like fixes did not work, because the terminal may be running `ant-code-latest` or another global install instead of `lab-agent`.

For continuation work, always launch explicitly from `lab-agent`:

```powershell
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui
```

Do not rely on:

```powershell
ant-code tui
```

unless the executable path has been checked and confirmed to point at `lab-agent`.

## Clean-Room Boundary

Do not read, copy, or port implementation code from `ant-code-latest` while implementing `lab-agent`.

Allowed uses:

- User-described observable behavior.
- Logs, screenshots, or interaction notes that describe behavior rather than code.
- Clean-room behavior specifications already written into this repository.
- Public documentation and public open-source alternatives.
- Reviewer-only notes that have been sanitized into behavior requirements.

Disallowed uses:

- Reading source files from `ant-code-latest` to implement features.
- Copying file layout, component names, state machine names, or code structure from `ant-code-latest`.
- Running tests against `ant-code-latest` and assuming they validate `lab-agent`.

The key distinction: `ant-code-latest` is the main reference for target behavior, but `lab-agent` must remain an independently authored clean-room implementation.

## Practical Debug Checklist

When a live TUI fix appears to have no effect:

1. Confirm terminal path:

   ```powershell
   Get-Location
   ```

2. Confirm launch command:

   ```powershell
   node .\src\cli\index.js tui
   ```

3. If using a global command, inspect its target first.
4. Re-test from `C:\saveproject\LBJ-workspace\lab-agent`.
