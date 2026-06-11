# TaxaMask

**TaxaMask** is an open-source workbench for taxonomy and morphology research. It organizes literature trait descriptions, specimen image annotation, AI pre-annotation, human review, model training, and dataset export into one traceable research workflow.

TaxaMask comes from real ant taxonomy work: researchers often move back and forth between specimen images, morphological characters, taxonomic papers, species descriptions, figure captions, manual masks, and machine-learning training data. TaxaMask connects those scattered steps into composable workflow entry points, so researchers can start from VLM drafts or coarse model predictions, review them manually, and gradually build reliable training material for more stable fine-grained annotation.

The embedded **Agent Center** is a core part of the design. Instead of asking researchers to read a long software manual before they can work, TaxaMask lets users ask a local agent about project state, model configuration, error messages, PDF screening, training plans, and workflow adaptation in natural language. TaxaMask does not define one fixed taxonomy workflow; researchers can shape the workflow with the agent around their own taxon, image material, literature trait descriptions, annotation targets, and available models.

Ant morphology is the most validated reference route in the current public release. Other taxa with morphology annotation needs can be adapted by copying and validating profiles on small batches before scaling up.

## Core Ideas

- **Candidate material is separated from training truth.** Figures extracted from PDFs, VLM drafts, and model predictions are never treated as confirmed training labels automatically. Human review remains part of the workflow boundary.
- **Agent Center is built into the workbench.** Researchers can use natural language to inspect state, configure model backends, triage errors, plan PDF screening or training, and adapt TaxaMask to their own research habits.
- **Profiles adapt the workflow without binding it to one taxon.** Ant morphology is the strongest reference workflow, while PDF screening rules, figure review rules, part labels, and model backends can be copied and tuned for other morphology-focused projects.

## Who It Is For

TaxaMask is intended for researchers who need to connect literature trait descriptions, morphology images, and machine-learning training data, including:

- Ant, Formicidae, insect, and other morphology-focused taxonomy projects.
- Species descriptions, taxonomic revisions, plate organization, and morphology review.
- Mask annotation for heads, mesosoma, gaster, appendages, and other specimen structures.
- Extracting figures, captions, and literature trait descriptions from existing or newly screened PDF papers.
- Preparing traceable, human-reviewed datasets for SAM, YOLO, COCO, or multimodal models.
- Iterating from VLM pre-annotation to human review, model training, prediction review, and dataset export.

## Keywords

Taxonomic image annotation, morphological mask segmentation, VLM pre-annotation, AI-assisted annotation, human-in-the-loop review, automated fine-grained annotation, agent-assisted taxonomy workflow, literature trait descriptions, ant taxonomy, Formicidae, insect taxonomy, species description, taxonomic revision, PDF literature screening, figure extraction, caption extraction, training dataset generation, SAM-assisted annotation, COCO export, YOLO export, biodiversity informatics.

## What TaxaMask Does

TaxaMask connects the daily research loop around specimens, literature, annotations, and training data:

```text
Agent Center -> PDF literature processing or 2D/STL morphology work
-> candidate review -> annotation / model drafts -> human confirmation -> dataset export
```

Main capabilities:

- Embedded TaxaMask Agent Center powered by the bundled Ant-Code dashboard for workflow guidance, error triage, configuration checks, and guarded source or model-adapter changes.
- PDF literature screening with editable taxonomy profiles.
- Figure and caption extraction with accepted and needs-review output folders.
- Pure-text PDF literature trait-description extraction into provenance-backed `taxon -> part -> description` records.
- 2D morphology annotation with parent-part and child-part work areas.
- STL-derived rendered views treated as reviewable 2D morphology images, with source provenance preserved.
- SAM-assisted annotation and VLM first-mile draft boxes for human review.
- Route-specific child-part experts through Blink, heatmap Blink, or external Blink backends.
- Built-in and external model backend contracts for parent-part and child-part workflows.
- Dataset export to multimodal JSONL, COCO, and YOLO-style formats, including a model-profile summary for audit.

TaxaMask does not include model weights, private datasets, local projects, API keys, run outputs, or user runtime configuration.

## Current Public Scope

The public v1.0 release focuses on these routes:

- `TaxaMask Agent Center`: embedded natural-language agent workbench for workflow definition, project-state inspection, model configuration, error triage, profile adaptation, and external-model planning.
- `PDF Evidence`: screen PDFs, extract figures, captions, and literature trait descriptions, then import reviewed candidate images into 2D projects.
- `2D/STL Morphology`: annotate ordinary images and STL-derived rendered 2D views in the Labeling Workbench.
- `Blink / Child-Part Refinement`: train or call route-specific child-part experts from parent-region context.
- `VLM Drafts`: generate reviewable first-mile boxes and optional SAM draft polygons for selected structures.
- `External Backends`: connect custom parent or child models through documented JSON contracts.

## License

TaxaMask source code is licensed under the GNU Affero General Public License v3.0. Commercial use is allowed under the license, but modified versions and network services must comply with AGPLv3 source-disclosure obligations. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

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

If the GUI cannot start after local source-code changes, the bundled Ant-Code dashboard can still be launched without importing the PySide6 GUI:

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

On Windows, `启动AntCode修复面板.bat` runs the same recovery route with extra Node.js discovery. Ubuntu/Linux or WSL terminal users can run:

```bash
bash ./启动AntCode修复面板.sh
```

All of these options require Node.js 20 or newer and the `vendor/ant-code` dependencies installed with `npm ci`.

On Ubuntu/WSL, TaxaMask opens the Ant-Code Dashboard in an external browser by default instead of embedding Qt WebEngine. This avoids crashes seen on some Linux/WSLg EGL/OpenGL driver stacks. If your local Qt WebEngine is known to be stable, set `TAXAMASK_ANTCODE_BROWSER_MODE=0` to restore embedded mode. In browser mode, TaxaMask's "Ask Agent" buttons open the browser and copy the current workbench context to the clipboard so it can be pasted into the Ant-Code prompt before sending.

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
vendor/ant-code/            Embedded Agent Center runtime
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

Until a DOI or paper is available, cite the GitHub repository and release version:

```text
TaxaMask: a taxonomy-oriented mask annotation and multimodal dataset workbench.
GitHub repository, version v1.0.0.
```
