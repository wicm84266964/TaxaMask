# TaxaMask

[![DOI](https://zenodo.org/badge/1264598942.svg)](https://doi.org/10.5281/zenodo.20619867)

**TaxaMask** is an open-source desktop workbench for traceable biological morphology annotation and AI training dataset construction.

TaxaMask connects taxonomic literature, specimen images, AI drafts, human-reviewed labels, model training, and dataset export in one provenance-aware project loop. It was developed from ant morphology research and is designed for morphology-focused taxonomy projects that need reliable annotation records, reusable training data, and clear links between source material and exported datasets.

TaxaMask also includes an embedded **Agent Center**. Researchers can use natural language to inspect project state, understand errors, adjust profiles, configure model backends, and modify project code after confirmation. This lets each lab reshape TaxaMask around its own taxa, image sources, annotation targets, and local model setup.

## Visual Overview

![TaxaMask workflow overview](docs/assets/readme/figure_1_taxamask_workflow.png)

TaxaMask keeps source materials, candidate images, AI drafts, human-confirmed labels, exported datasets, and model feedback connected through project records. Researchers can move from literature screening and image extraction to annotation, review, training, prediction checking, and dataset export while preserving provenance.

## Two Main Threads

### 1. Traceable Morphology Annotation and Training Data

TaxaMask organizes taxonomic material by state: source materials, candidate materials, AI drafts, human-confirmed labels, and exported datasets are recorded as separate layers in the project. PDF figures, captions, literature trait descriptions, specimen images, STL-rendered views, VLM boxes, SAM masks, model predictions, and human masks can enter the same review chain without being merged automatically into training truth.

This thread focuses on where morphology training data comes from, how it has been processed, and which labels have been confirmed by a researcher. TaxaMask supports:

```text
Agent Center -> PDF literature processing or 2D/STL morphology work
-> candidate review -> annotation / model drafts -> human confirmation -> dataset export
```

- PDF literature screening with editable taxonomy profiles.
- Figure and caption extraction with accepted and needs-review output folders.
- Literature trait-description extraction into provenance-backed `taxon -> part -> description` records.
- 2D morphology annotation with parent-part and child-part work areas.
- STL-derived rendered views treated as reviewable 2D morphology images.
- VLM first-mile draft boxes and optional SAM-assisted draft masks.
- Human review loops for AI drafts and external model predictions.
- Route-specific child-part experts through Blink, heatmap Blink, or external Blink backends.
- Built-in and external model backend contracts for parent-part and child-part workflows.
- Dataset export to multimodal JSONL, COCO, and YOLO-style formats.

### 2. Agent-Assisted Project Modification

TaxaMask includes an embedded Agent Center. It can read project records, profiles, runtime logs, backend contracts, and relevant source-code context, then turn natural-language requests into concrete changes for the researcher to confirm. Researchers can use it to inspect project state, understand errors, adjust profiles, configure model backends, and modify adapters, launchers, or related source files after confirmation.

This thread focuses on how different labs can reshape TaxaMask around their own projects. Researchers can ask for help with questions and changes such as:

- What is the current project state?
- Which profile or model backend is being used?
- Why did a PDF screening, VLM draft, or training step fail?
- How should a new taxon, body-part vocabulary, or local model route be configured?
- Which profile, adapter, launcher, or source file needs to change for this project?
- Can TaxaMask add or adjust a workflow entry point for this lab's annotation route?

Scientific decisions and final code changes stay under researcher control. TaxaMask does not include model weights, private datasets, local projects, API keys, run outputs, or user runtime configuration.

![TaxaMask public interface overview](docs/assets/readme/figure_2_taxamask_ui_overview.png)

The public interface centers on four practical entry points: Agent Center for local workflow help, PDF extraction setup for literature evidence, candidate review for screening imported material, and the Labeling Workbench for reviewable morphology annotation.

Recovery note: source-code changes can break the GUI before the embedded Agent Center can open again. In that case, use the standalone Ant-Code recovery panel: run `启动AntCode修复面板.bat` on Windows, or `bash ./启动AntCode修复面板.sh` on Ubuntu/Linux/WSL, then continue debugging and editing from the browser-based dashboard. The dashboard can also load the Ant-Code chat history for the current project.

## Intended Use

TaxaMask is intended for researchers who need to connect biological morphology, taxonomic literature, specimen images, and AI-assisted annotation. It is especially relevant to species descriptions, taxonomic revisions, figure-plate organization, morphology mask annotation, and small research teams that need traceable links between source materials, annotation decisions, model drafts, and exported training data.

## Review Loop and Reference Route

![Human-in-the-loop annotation cycle in TaxaMask](docs/assets/readme/figure_3_human_in_the_loop_cycle.png)

TaxaMask treats VLM boxes, SAM masks, locator predictions, and external backend outputs as draft material until a researcher reviews them. This keeps AI assistance useful while keeping generated candidates separate from ground-truth labels.

![Ant morphology reference workflow](docs/assets/readme/figure_4_ant_morphology_case.png)

The current public release is most extensively validated on ant morphology workflows. In the reference case, TaxaMask was used to organize literature screening, image extraction, VLM first-mile pre-annotation, human review, parent-part annotation, training, prediction review, and dataset export.

Other taxa can use the same workflow pattern by adapting profiles, reviewing small batches first, and validating model behavior before scaling up.

## Keywords

Biological morphology annotation, taxonomic image annotation, traceable workflow, dataset provenance, AI-assisted annotation, human-in-the-loop review, VLM pre-annotation, SAM-assisted annotation, morphology segmentation, taxonomic literature, species description, figure extraction, caption extraction, training dataset construction, agent-assisted workflow, source-code assisted customization, customizable annotation workflow, biodiversity informatics, ant taxonomy, Formicidae.

## License

TaxaMask source code is licensed under the GNU Affero General Public License v3.0. Commercial use is allowed under the license, but modified versions and network services must comply with AGPLv3 source-disclosure obligations. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

The bundled Ant-Code Agent Center under `vendor/ant-code/` is first-party TaxaMask source code. The directory name is retained for runtime layout compatibility; it should not be interpreted as a third-party dependency or excluded from attribution for the TaxaMask project.

If TaxaMask helps your research, please cite the repository or release. See [CITATION.cff](CITATION.cff).

## Platform Support

TaxaMask is distributed as source-based research software.

- Windows 10/11 is the primary validated desktop environment.
- Linux is the main target for lab workstations, CUDA training, and batch processing.
- macOS can be tried for lightweight CPU-oriented review, but Apple Silicon acceleration is not a validated v1.0 target.

Install the PyTorch build that matches your machine before installing the base dependencies.

## Installation

Prerequisites:

- Git for cloning the source repository, or a GitHub ZIP download.
- Conda or another Python environment manager.
- Python 3.12 is the recommended tested version for the public source release.
- Node.js 20 or newer with npm for the embedded Agent Center / Ant-Code dashboard.

Clone the source repository first:

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

If Git is unavailable, download the repository ZIP from GitHub, extract it, and open a terminal in the extracted `TaxaMask` folder.

Then create a Python environment. The recommended Conda environment name is `taxamask`:

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

Install PyTorch first. For CPU-only testing:

```bash
pip install -r requirements-torch-cpu.txt
```

For NVIDIA CUDA 12.1:

```bash
pip install -r requirements-torch-cu121.txt
```

Then install the base dependencies:

```bash
pip install -r requirements.txt
```

Install the bundled Agent Center dependencies:

```bash
cd vendor/ant-code
npm ci
cd ../..
```

This step is required for the embedded Ant-Code dashboard and the recovery panel. The repository does not include `node_modules`.

Optional SAM-assisted annotation requires a SAM checkpoint placed at:

```text
AntSleap/weights/sam_b.pt
```

Weights are not included in the repository.

PDF processing can use PyMuPDF directly, but some fallback image-extraction paths require Poppler through `pdf2image`. See [Platform setup](docs/platform_setup.md) for platform-specific Poppler notes.

TaxaMask can start without API keys. The Agent Center dashboard can open without a model key, but model-backed chat, VLM drafts, and external model routes require a local model gateway or API settings configured on the user's machine. Do not commit real keys, private gateway URLs, or runtime settings.

## Update

If you already cloned the repository, update to the latest source fixes with:

```bash
git pull --ff-only origin main
```

After an update, rerun `pip install -r requirements.txt` or `npm ci` inside `vendor/ant-code` only when the dependency files have changed.

## Run

From an activated environment:

```bash
python AntSleap/main.py
```

On Windows, `启动TaxaMask.bat` searches for a local `.venv`, an active Conda environment, common `taxamask` Conda locations, and Python on `PATH`. You can override discovery with:

```bat
set TAXAMASK_PYTHON_EXE=C:\path\to\python.exe
```

Ubuntu/Linux or WSL terminal users can use the shell launcher:

```bash
bash ./启动TaxaMask.sh
```

If local source-code changes prevent the GUI from starting, launch the bundled Ant-Code dashboard without importing the PySide6 GUI:

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

On Windows, `启动AntCode修复面板.bat` runs this recovery route with extra Node.js discovery. Ubuntu/Linux or WSL terminal users can run:

```bash
bash ./启动AntCode修复面板.sh
```

The browser-based dashboard can continue code review, edits, and debugging when the TaxaMask GUI cannot import. It can also load Ant-Code chat history for the current project. All of these options require Node.js 20 or newer and the `vendor/ant-code` dependencies installed with `npm ci`.

On Ubuntu/WSL, TaxaMask opens the Ant-Code dashboard in an external browser by default instead of embedding Qt WebEngine. This avoids crashes seen on some Linux/WSLg EGL/OpenGL driver stacks. If your local Qt WebEngine is known to be stable, set `TAXAMASK_ANTCODE_BROWSER_MODE=0` to restore embedded mode. In browser mode, TaxaMask's "Ask Agent" buttons open the browser and copy the current workbench context to the clipboard so it can be pasted into the Ant-Code prompt before sending.

If the TaxaMask GUI is launched by Windows Python but Ant-Code / Node dependencies are installed inside WSL Ubuntu, start the GUI with the WSL runtime bridge enabled:

```bash
# Run once inside Ubuntu / WSL
cd /mnt/c/path/to/TaxaMask/vendor/ant-code
npm ci
```

```bat
set TAXAMASK_ANTCODE_RUNTIME=wsl
set TAXAMASK_WSL_DISTRO=Ubuntu
启动TaxaMask.bat
```

If your distribution is not named `Ubuntu`, use the name shown by `wsl -l -v`. For unusual mount layouts, set `TAXAMASK_WSL_PROJECT_DIR=/home/.../TaxaMask` as an explicit Linux-side project path.

## Repository Layout

```text
AntSleap/                  Python package and Qt workbench
core/pdf_processor/         PDF screening and extraction logic
tools/agentic/              Headless PDF, candidate, VLM, and export tools
tools/governance/           Dataset governance and audit helpers
screener_configs/           PDF screening templates and examples
multimodal_configs/         Figure extraction / review profiles
part_description_configs/   PDF literature trait-description extraction profiles
json_projects/templates/    Clean project templates
docs/contracts/             External backend contracts
vendor/ant-code/            First-party Ant-Code Agent Center runtime
tests/                      Unit and workflow tests
TaxaMask使用手册.md           Chinese public user manual
README_zh.md                Chinese public README
```

The internal package name `AntSleap` is kept for runtime stability and as a tribute to the SLEAP project that inspired the original direction. The public project name is TaxaMask.

## Typical Workflow

1. Start TaxaMask and enter the Agent Center.
2. Use PDF Evidence to screen papers and extract figures, captions, and literature trait descriptions.
3. Import reviewed candidate images or ordinary morphology images into a 2D project.
4. Annotate parent structures and child structures in the Labeling Workbench.
5. Use VLM or SAM outputs only as reviewable drafts.
6. Train or connect workflow-specific parent and child backends.
7. Review predictions manually.
8. Export multimodal, COCO, or YOLO-style datasets.

## Profile Adaptation

For a new taxon, copy and edit the relevant templates rather than changing examples in place:

- PDF screening: `screener_configs/`
- Figure extraction and multimodal review: `multimodal_configs/`
- PDF literature trait-description extraction: `part_description_configs/`
- Project templates: `json_projects/templates/`

Start with a small batch before large-scale runs. Profile behavior must be validated for each taxon.

## External Backend Contracts

- [Parent-part external backend contract](docs/contracts/external_backend_contract_v1.md)
- [Child-part Blink external backend contract](docs/contracts/external_blink_backend_contract_v1.md)

External backend predictions are review candidates. They should not be treated as confirmed training truth until checked by a researcher.

## Documentation

- [中文 README](README_zh.md)
- [Chinese user manual](TaxaMask使用手册.md)
- [Platform setup](docs/platform_setup.md)
- [PDF screening profile guide](docs/PDF筛选profile适配说明.md)
- [Figure extraction and multimodal profile guide](docs/图文提取与多模态profile适配说明.md)
- [Parent backend contract](docs/contracts/external_backend_contract_v1.md)
- [Child Blink backend contract](docs/contracts/external_blink_backend_contract_v1.md)

## Citation

If TaxaMask helps your research, please cite the software release:

```text
TaxaMask: a taxonomy-oriented mask annotation and multimodal dataset workbench.
Zenodo DOI (all versions): https://doi.org/10.5281/zenodo.20619867
```
