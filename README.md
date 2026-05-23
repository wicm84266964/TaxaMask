# TaxaMask

TaxaMask is a research workbench for taxonomy-oriented mask annotation, literature figure extraction, and multimodal dataset production.

It was originally built for ant taxonomy research, with an ant morphology workflow as the most validated example. The current architecture also exposes configurable profiles and templates for other biological taxa, so researchers can adapt PDF screening, figure extraction, structure labels, model training, and dataset export to their own organisms.

> License note: TaxaMask is released for academic and research use. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [CITATION.cff](CITATION.cff) before redistribution or reuse.

## What TaxaMask Does

TaxaMask connects four parts of a taxonomy data workflow:

- Agent-assisted operation: use the embedded Ant-Code Agent Center to configure workflows, inspect errors, prepare PDF evidence runs, adapt custom model backends, and plan training without asking domain researchers to write Python commands. Fixed `Ask Agent` entry points pass compact routing cards that point the Agent to relevant docs, source files, contracts, logs, and safety boundaries instead of dumping large project data into chat; external backend edits and TaxaMask source edits use separate confirmation levels.
- Literature processing: screen taxonomy PDFs, extract candidate figures, assemble caption and nearby text evidence, and optionally run multimodal review.
- Annotation and model loop: manage project images and STL-derived rendered views, draw masks, use SAM-assisted annotation, use parent-child Blink refinement inside the main Labeling Workbench, train locator/SAM/Blink components, reuse trained experts for pre-annotation, and export datasets.
- Ant 3D workbench: keep STL-derived 2D review and TIF volume segmentation as separate workflows, import AMIRA/TIF volume data, preserve material maps and manual truth layers, and export volume labels for external 3D segmentation backends.

The intended research loop is:

```text
Agent Center -> choose PDF / 2D-STL / TIF workflow
-> evidence or annotation -> model training / prediction -> human review -> dataset export
```

## Main Features

- PDF screening with editable V2 logic profiles.
- Figure extraction and multimodal review profiles for different taxa or plate styles.
- Embedded TaxaMask Agent Center powered by a local Ant-Code dashboard, with workflow shortcuts for 2D/STL morphology and TIF volume projects.
- Taxa-aware project templates, including a validated ant morphology example and a generic taxonomy mask template.
- Labeling Workbench for biological structure masks, including specimen-grouped STL-rendered surface views imported as derived 2D review images, plus integrated parent-child Blink refinement for small structures.
- TIF Volume Workbench for stack viewing, overlay review, material-map editing, working edits, and explicit promotion to manual training truth.
- Route-appointed Blink experts for parent-structure to child-structure pre-annotation, shrink-trajectory generation, and local expert training from the main 2D/STL labeling surface.
- Configurable main locator structures for non-ant projects.
- Built-in training/inference path plus an external backend contract for advanced users who want to connect custom models.
- Guarded custom-model adaptation: external backend scripts/configs can be approved separately from TaxaMask source development, so users know when they are changing a model adapter versus changing the program itself.
- Export paths for multimodal JSONL, COCO, YOLO-style datasets, and TIF volume exchange formats including OME-TIFF, NRRD, MHA, NIfTI, nnU-Net-style layout, and MONAI-style datalists.
- Headless agentic tools for PDF screening, figure extraction, candidate import, auto-annotation, and dataset export.

## Current Workbench Entry Points

The GUI starts at the TaxaMask Agent Center by default. The center area embeds the Ant-Code dashboard for natural-language task assistance, while the right rail exposes direct workflow cards:

- `2D/STL Morphology`: ordinary 2D morphology images and STL-derived rendered 2D views. This route uses the Labeling Workbench with an integrated parent-child Blink refinement panel, built-in Locator/SAM, route-appointed experts, and the 2D external backend contract.
- `TIF Volume`: continuous TIF/AMIRA-style volumes. This route uses independent TIF projects, material-ID label fields, `manual_truth` / `working_edit` / `model_draft` layers, TIF exports, and the TIF backend contract.
- `PDF Evidence`: available through Agent/headless tools and `File -> Open PDF Evidence Tools`. PDF outputs are evidence/provenance artifacts, not automatic training truth.

Locator and SAM are lazy-loaded. Starting the app or entering the TIF workflow does not load them; entering the 2D/STL workflow preloads them, and returning to the Agent Center keeps already loaded models alive.

## Current Validation Scope

TaxaMask is multi-taxon configurable, but not all taxa are equally validated.

- Ant morphology is the best-tested reference workflow.
- Generic and plant profiles are provided as adaptation templates.
- New taxa should be validated with a small PDF/image batch before large-scale runs.
- Custom model backends should be tested with a small project before production use.

This distinction matters for research trustworthiness: the software exposes adaptation interfaces, but each new taxon still needs profile-level and model-level validation.

## Platform Support

TaxaMask is currently prepared as a source-based research application.

- Windows 10/11 is the primary validated desktop environment.
- Linux is the main cross-platform target for lab workstations, servers, CUDA training, and batch processing.
- macOS is planned as a CPU-only source-based trial path for lightweight annotation, project review, teaching, and small validation runs.
- Apple Silicon MPS acceleration is not part of the first compatibility target because SAM, torchvision, Ultralytics, and related model paths need real-machine testing before they can be trusted.

Users may install a PyTorch build that fits their own hardware before installing the base dependencies. Advanced users can experiment with their own compatible PyTorch/SAM stack, but the current validated training path remains Windows/Linux with CPU or NVIDIA CUDA.

For detailed per-platform notes, see [Platform setup](docs/platform_setup.md).

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

1. Create and activate a Python environment.
2. Install a PyTorch variant for your machine first. For CPU-only testing:

```bash
pip install -r requirements-torch-cpu.txt
```

For NVIDIA CUDA 12.1 environments, such as a matching Windows or Linux workstation:

```bash
pip install -r requirements-torch-cu121.txt
```

Linux CUDA users should choose the PyTorch command that matches their installed driver and CUDA runtime when the CUDA 12.1 example is not appropriate. macOS users should not install the CUDA requirements file.

3. Install the base dependencies:

```bash
pip install -r requirements.txt
```

4. Download the SAM base checkpoint if you want SAM-assisted annotation, and place it under:

```text
AntSleap/weights/sam_b.pt
```

Model weights are not included in the repository.

Linux and macOS users may also need system packages for Qt/PySide6 display support and Poppler-based PDF tooling. These requirements differ by distribution and package manager; see [Platform setup](docs/platform_setup.md).

## Run the GUI

```bash
python AntSleap/main.py
```

The main window title should show:

```text
TaxaMask Workbench
```

## Typical Workflow

1. Start in the Agent Center and choose whether the task is PDF evidence, 2D/STL morphology, or TIF volume annotation.
2. For PDF evidence, configure API/profile settings and run a small batch before scaling.
3. For 2D/STL morphology, create/open a 2D project, import ordinary images or STL-rendered views, then annotate in the Labeling Workbench.
4. For child structures, use the Labeling Workbench's `Parent-child refinement / Blink` panel to pick the parent context, configure the route expert, auto-annotate, generate shrink trajectories, and train the current child expert.
5. For TIF volume work, create/open a TIF project, import TIF stacks or AMIRA directories, review material maps, and promote reviewed edits to `manual_truth`.
6. Train or connect the workflow-specific backend.
7. Run pre-annotation/prediction, review results, and export a dataset or training handoff.

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
