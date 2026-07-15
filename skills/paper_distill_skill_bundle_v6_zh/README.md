# Paper Distill Skill Bundle

This bundle contains the standalone `app.paper_distill` subsystem and the host-agnostic `skills/paper_distill/SKILL.md` contract.

This is the TaxaMask Chinese-first variant, version `0.2.0+taxamask.zh1`. It is selectively maintained from the standalone Paper Distill project rather than treated as the same `0.2.0` behavior.

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
