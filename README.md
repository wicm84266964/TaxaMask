# TaxaMask

TaxaMask is a research workbench for taxonomy-oriented mask annotation, literature figure extraction, and multimodal dataset production.

It was originally built for ant taxonomy research, with an ant morphology workflow as the most validated example. The current architecture also exposes configurable profiles and templates for other biological taxa, so researchers can adapt PDF screening, figure extraction, structure labels, model training, and dataset export to their own organisms.

> License note: TaxaMask is released for academic and research use. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [CITATION.cff](CITATION.cff) before redistribution or reuse.

## What TaxaMask Does

TaxaMask connects two parts of a taxonomy data workflow:

- Literature processing: screen taxonomy PDFs, extract candidate figures, assemble caption and nearby text evidence, and optionally run multimodal review.
- Annotation and model loop: manage project images, draw masks, use SAM-assisted annotation, train locator/SAM/Blink components, reuse trained experts for pre-annotation, and export datasets.

The intended research loop is:

```text
PDF literature -> candidate figures -> project images -> mask annotation
-> model training -> automatic pre-annotation -> human review -> dataset export
```

## Main Features

- PDF screening with editable V2 logic profiles.
- Figure extraction and multimodal review profiles for different taxa or plate styles.
- Taxa-aware project templates, including a validated ant morphology example and a generic taxonomy mask template.
- Labeling Workbench for biological structure masks.
- Blink Workbench for parent-structure to child-structure refinement and local expert training.
- Configurable main locator structures for non-ant projects.
- Built-in training/inference path plus an external backend contract for advanced users who want to connect custom models.
- Export paths for multimodal JSONL, COCO, and YOLO-style datasets.
- Headless agentic tools for PDF screening, figure extraction, candidate import, auto-annotation, and dataset export.

## Current Validation Scope

TaxaMask is multi-taxon configurable, but not all taxa are equally validated.

- Ant morphology is the best-tested reference workflow.
- Generic and plant profiles are provided as adaptation templates.
- New taxa should be validated with a small PDF/image batch before large-scale runs.
- Custom model backends should be tested with a small project before production use.

This distinction matters for research trustworthiness: the software exposes adaptation interfaces, but each new taxon still needs profile-level and model-level validation.

## Repository Layout

```text
AntSleap/                  Internal Python package and Qt workbench
core/pdf_processor/         PDF screening, figure extraction, multimodal validation
tools/agentic/              Headless workflow tools
tools/governance/           Dataset governance and audit utilities
screener_configs/           PDF screening profile examples and templates
multimodal_configs/         Figure extraction and multimodal review profiles
json_projects/templates/    Clean project templates
docs/                       Public profile guides and external contracts
tests/                      Unit and workflow tests
TaxaMask使用手册.md           Chinese user manual
```

The internal package is still named `AntSleap` for runtime stability and historical compatibility. The public project name is TaxaMask.

## Installation

TaxaMask is currently prepared as a source-based research application.

1. Create and activate a Python environment.
2. Install a PyTorch variant for your machine first:

```bash
pip install -r requirements-torch-cpu.txt
```

or, for CUDA 12.1:

```bash
pip install -r requirements-torch-cu121.txt
```

3. Install the base dependencies:

```bash
pip install -r requirements.txt
```

4. Download the SAM base checkpoint if you want SAM-assisted annotation, and place it under:

```text
AntSleap/weights/sam_b.pt
```

Model weights are not included in the repository.

Windows is the primary validated desktop environment at this stage. Linux and macOS should be treated as experimental until real-machine validation covers Qt startup, PyTorch, Poppler/PDF tooling, and file-open behavior. macOS can use CPU mode for small tests; Apple Silicon MPS acceleration is not yet exposed as a runtime device option.

## Run the GUI

```bash
python AntSleap/main.py
```

The main window title should show:

```text
TaxaMask Workbench
```

## Typical Workflow

1. Configure text and multimodal API settings if you plan to use LLM-assisted PDF processing.
2. Choose a PDF screening profile in `PDF Processing -> Select Logic Profile`.
3. Choose a figure extraction/review profile for image and caption evidence handling.
4. Run a small PDF batch and inspect accepted/review/rejected results.
5. Create or open a TaxaMask project.
6. Import candidate images into the project.
7. Annotate main structures in the Labeling Workbench.
8. Use Blink for child structures that need local parent-context refinement.
9. Train or connect a backend model.
10. Run pre-annotation, review predictions, and export a dataset.

See [TaxaMask使用手册.md](TaxaMask使用手册.md) for the detailed Chinese manual.

## Adapting to Other Taxa

For a new organism group, usually adapt these layers:

- PDF screening: copy a file from `screener_configs/` and edit target taxa, keywords, and prompt logic.
- Figure extraction and review: copy a file from `multimodal_configs/` and edit figure evidence rules, expected views, and review prompt.
- Project template: choose the generic taxonomy template and define your own structures.
- Main locator structures: keep large, stable structures in the main locator scope; use Blink or custom backends for small local parts.
- Model backend: use the built-in path when it fits your structure model, or connect custom scripts through the external backend contract.

Profile guides:

- [PDF screening profile guide](docs/PDF筛选profile适配说明.md)
- [Figure extraction and multimodal profile guide](docs/图文提取与多模态profile适配说明.md)
- [External backend contract](docs/contracts/external_backend_contract_v1.md)

## Headless Tools

Examples:

```bash
python tools/agentic/screen_pdfs.py --pdf-source-dir pdf_folder --out out_folder --config screener_configs/蚂蚁新种筛选_V2示例.json
```

```bash
python tools/agentic/extract_figures.py --pdf-source-dir pdf_folder --db out_folder/literature.db --out out_folder --figure-profile multimodal_configs/蚂蚁三视图提取复核_示例.json
```

```bash
python tools/agentic/run_agentic_pipeline.py --dry-run --out artifacts/agentic_pipeline
```

## Documentation

- [Chinese user manual](TaxaMask使用手册.md)
- [PDF screening profile guide](docs/PDF筛选profile适配说明.md)
- [Figure extraction and multimodal profile guide](docs/图文提取与多模态profile适配说明.md)
- [External backend contract](docs/contracts/external_backend_contract_v1.md)
- [Chinese changelog](CHANGELOG_zh.md)

## Citation

If TaxaMask helps your research, please cite the software repository and the associated DOI/release when available. See [CITATION.cff](CITATION.cff).

Until a DOI or paper is available, cite the GitHub repository and release version:

```text
TaxaMask: a taxonomy-oriented mask annotation and multimodal dataset workbench.
GitHub repository, version v0.1.0.
```

## License

TaxaMask is distributed under a research-use license inspired by the early academic release style of SLEAP. See [LICENSE](LICENSE).

Documentation and non-code explanatory materials are provided for research and academic reuse with attribution under the documentation terms in [NOTICE](NOTICE), unless a file states otherwise.

For commercial use, contact the author for separate permission.
