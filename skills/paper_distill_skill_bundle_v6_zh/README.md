# Paper Distill Skill Bundle

This bundle contains the standalone `app.paper_distill` subsystem and the host-agnostic `skills/paper_distill/SKILL.md` contract.

## Key behavior

- Distills one markdown paper at a time
- Exports `json`, `jsonl`, and `conversation-jsonl`
- Writes knowledge maps, conversation plans, and training conversations in Chinese even when the source paper is in English

## Install

```powershell
python -m pip install -e .
```

## Entrypoint

```powershell
paper-distill --help
```
