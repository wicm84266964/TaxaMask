# Contributing to TaxaMask

TaxaMask is currently maintained as research software. Contributions are welcome when they improve reproducibility, documentation clarity, taxonomic adaptability, or workflow reliability.

## Good Contribution Areas

- Bug reports with clear reproduction steps.
- Documentation fixes.
- New PDF screening profiles for additional taxa.
- New figure extraction or multimodal review profiles.
- Small tests that protect existing workflows.
- External backend examples that follow `docs/contracts/external_backend_contract_v1.md`.

## Before Opening a Pull Request

Please make sure that:

- No API keys, local project JSON files, databases, model weights, or generated run artifacts are included.
- New profile files do not contain private paths or unreleased data.
- New taxa or model workflows are described with their validation scope.
- Code changes include focused tests when they affect workflow behavior.

## Validation

Useful checks:

```bash
python -m unittest discover tests
```

For smaller changes, run the relevant test module and include the command in your pull request notes.

## Citation and Attribution

Derived research outputs should cite TaxaMask according to `CITATION.cff`. Modified versions should clearly state that they are based on TaxaMask and describe the changes made.
