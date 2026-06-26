# TaxaMask Developer Preview

[![DOI](https://zenodo.org/badge/1264598942.svg)](https://doi.org/10.5281/zenodo.20619867)

[中文 README](README_zh.md)

**TaxaMask** is an open-source desktop workbench for traceable biological morphology annotation, evidence review, and AI training dataset construction.

This branch is a **developer preview**. It keeps the stable TaxaMask 2D morphology and PDF evidence workflows, and adds the newer TIF/CT 3D workflow for internal morphology review, part-volume extraction, and local-axis reslicing. The 3D route has been developed and tested mainly with AntScan ant CT data. Its data structures are not hard-coded to ants, but broad multi-taxon validation is not yet claimed.

## Release 1.2.0 TIF Developer Preview

This branch release is published as `v1.2.0-tif-preview`. It keeps the stable 2D SQLite project-storage upgrade from TaxaMask 1.2.0 and additionally includes the TIF/CT SQLite project index, TIF annotation-tool polish, and local-axis developer-preview workflow.

The stable `v1.2.0` tag remains the 2D-focused release. See [docs/releases/1.2.0-tif-preview.md](docs/releases/1.2.0-tif-preview.md) for the full branch release notes.

## What This Preview Contains

TaxaMask now has four connected research routes:

```text
PDF evidence
  -> figure/caption extraction
  -> candidate review
  -> traceable literature evidence

2D / STL morphology
  -> parent and child part annotation
  -> AI drafts and human review
  -> training dataset export

TIF / CT internal morphology
  -> specimen import
  -> part ROI and key-slice masks
  -> part volume extraction
  -> 3D preview and local-axis reslice export

Agent Center
  -> workflow inspection
  -> error explanation
  -> profile and backend help
  -> code changes after researcher confirmation
```

The program is designed around human-reviewed morphology data. AI outputs, imported predictions, and automated suggestions remain draft material until a researcher accepts them.

## TIF / CT Developer Preview

The TIF workbench is the main new preview area. It is intended for volumetric morphology tasks where the original scan direction, specimen posture, and target structure orientation vary between samples.

Current TIF/CT capabilities include:

- Importing a TIFF stack as a specimen.
- Viewing the full volume and extracted part volumes.
- Drawing part ROIs and key-slice contours.
- Interpolating masks between key slices.
- Accepting part masks and writing part-volume records.
- GPU 3D volume preview with clipping and section inspection.
- Z/Y/X slice navigation for multi-direction review.
- Local Axis Reslice for a selected part volume.
- Source Z-axis display as a locked reference.
- Editable output Z-axis for the reslice direction.
- Roll reference point pair for orientation standardization.
- Resliced grayscale TIFF export, with metadata JSON.
- Optional mask TIFF export when a part mask is available.
- Training-material records that capture manual part extraction and local-axis decisions for later model development.

The local-axis workflow is intentionally generic. The first validated template is brain/head oriented, but the module is named **Local Axis Reslice** and stores general local-frame metadata rather than brain-only fields.

Implementation note: the TIF/CT 3D preview is an independent TaxaMask implementation built for the PySide6 / PyOpenGL TIF workbench. It uses common GPU volume-rendering ideas such as 3D textures, transfer mapping, ray marching, clipping, and section inspection. The interaction target is informed by established scientific volume-visualization tools, including Drishti.

## Local Axis Reslice Concept

A reslice is saved under a specimen part, not as a modification of the original TIFF.

```text
specimen
  -> parts
     -> head
        -> mask
        -> contours
        -> reslices
           -> reslice item
              -> image.tif
              -> metadata.json
              -> mask.tif, when available
```

The original TIFF stack remains unchanged. A reslice records:

- source volume and part volume identity
- source Z-axis reference
- editable output Z-axis
- local frame: origin, x axis, y axis, z axis
- roll reference point pair
- spacing and interpolation settings
- export paths and provenance metadata

Grayscale image reslicing uses linear interpolation. Mask and label reslicing use nearest-neighbor interpolation.

## Agent Center

TaxaMask includes the first-party Ant-Code Agent Center under `vendor/ant-code/`. It helps inspect project state, explain errors, review profiles, and make code changes after confirmation.

Agent model credentials and private gateway settings are local runtime configuration. They are not included in this repository. The embedded runtime is pointed at:

```text
AntSleap/config/taxamask_ant_code.config.json
```

The GUI can start without API keys. Model-backed chat, VLM drafts, and external routes require local configuration on the user's machine.

## Data Boundary

TaxaMask is source code and public workflow documentation. Private CT stacks, local project files, exported results, model weights, runtime settings, API keys, and internal planning notes should stay on the user's machine and are ignored by default.

## Installation

TaxaMask is distributed as source-based research software.

Validated target environments:

- Windows 10/11 for the main desktop workflow.
- Linux workstations for CUDA training and batch processing.
- macOS can be tried for lightweight CPU review, but Apple Silicon acceleration is not a validated target.

Prerequisites:

- Git, or a GitHub ZIP download.
- Conda or another Python environment manager.
- Python 3.12.
- Node.js 20 or newer for the embedded Agent Center dashboard.

To install the public stable line, clone the default branch:

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

To install this TIF/CT developer preview from GitHub, select the `codex/antscan-stl-tif-rearchitecture` branch before downloading the ZIP, or clone the preview branch directly:

```bash
git clone --branch codex/antscan-stl-tif-rearchitecture --single-branch https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

Create and activate a Python environment:

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

Install the Agent Center dependencies:

```bash
cd vendor/ant-code
npm ci
cd ../..
```

Optional SAM-assisted 2D annotation requires a SAM checkpoint placed at:

```text
AntSleap/weights/sam_b.pt
```

Model weights are not included.

## Run

From an activated environment:

```bash
python AntSleap/main.py
```

Windows users can also run:

```bat
启动TaxaMask.bat
```

Linux or WSL users can run:

```bash
bash ./启动TaxaMask.sh
```

If source-code changes prevent the GUI from starting, launch the Agent Center recovery dashboard directly:

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

On Windows, `启动AntCode修复面板.bat` uses this recovery route.

### TIF / CT GPU Notes

The TIF/CT volume preview works best when the Python interpreter is assigned to the dedicated NVIDIA GPU. On Windows laptops or desktops with both integrated graphics and an NVIDIA card, set the selected `python.exe` to **High performance** in Windows Graphics settings or NVIDIA Control Panel. The `启动TaxaMask.bat` launcher now searches the `taxamask` Conda environment before the older `antsleap` environment, so update any `TAXAMASK_PYTHON_EXE` override if your environment name changed. After opening a TIF project, check the volume preview status line: it reports the active OpenGL renderer and makes integrated-GPU or CPU fallback problems visible.

## Repository Layout

```text
AntSleap/                  Python package and Qt workbenches
AntSleap/core/             Project, TIF, extraction, export, and backend logic
AntSleap/ui/               Desktop UI, 2D labeling, PDF, TIF, and Agent panels
core/pdf_processor/         PDF screening and extraction logic
tools/agentic/              Headless PDF, candidate, VLM, and export tools
tif_blink/                  TIF-local model route experiments and helpers
tif_blink_nnunet/           nnU-Net oriented TIF helper route
screener_configs/           PDF screening templates and examples
multimodal_configs/         Figure extraction and review profiles
part_description_configs/   Literature trait-description extraction profiles
json_projects/templates/    Clean project templates
docs/contracts/             Public backend and TIF local-axis contracts
vendor/ant-code/            First-party Agent Center runtime
tests/                      Unit and workflow tests
TaxaMask使用手册.md           Chinese user manual
```

The internal package name `AntSleap` is kept for runtime stability and as a tribute to the SLEAP project that inspired the original direction. The public project name is TaxaMask.

## Typical Workflows

PDF evidence route:

1. Configure or adapt a PDF screening profile.
2. Extract figures, captions, and literature trait descriptions.
3. Review accepted and needs-review outputs.
4. Import useful candidates into TaxaMask projects.

2D / STL morphology route:

1. Import specimen images or rendered STL views.
2. Annotate parent and child morphology structures.
3. Treat VLM, SAM, and model predictions as drafts.
4. Confirm labels manually.
5. Export training datasets.

TIF / CT route:

1. Open an AntScan or other TIFF stack.
2. Create a specimen part with ROI and key-slice masks.
3. Extract a part volume.
4. Review the part in 3D and multi-direction slices.
5. Copy the source Z-axis into an editable local output axis.
6. Set roll reference points for orientation standardization.
7. Export the resliced part TIFF and metadata.

## External Backend Contracts

- [Parent-part external backend contract](docs/contracts/external_backend_contract_v1.md)
- [Child-part Blink external backend contract](docs/contracts/external_blink_backend_contract_v1.md)
- [TIF local-axis backend contract](docs/contracts/tif_local_axis_backend_contract_v1.md)

External backend predictions are review candidates. They should not be treated as confirmed training truth until checked by a researcher.

## Documentation

- [Chinese README](README_zh.md)
- [Chinese user manual](TaxaMask使用手册.md)
- [Platform setup](docs/platform_setup.md)
- [PDF screening profile guide](docs/PDF筛选profile适配说明.md)
- [Figure extraction and multimodal profile guide](docs/图文提取与多模态profile适配说明.md)
- [External backend contracts](docs/contracts/)

## Keywords

taxonomy morphology annotation, biological image annotation, taxonomic literature evidence, PDF figure extraction, caption extraction, AI-assisted annotation, human-in-the-loop review, training dataset construction, COCO export, YOLO export, VLM pre-annotation, SAM-assisted annotation, STL morphology review, CT morphology, TIFF stack, TIF workbench, AntScan, 3D volume preview, GPU volume rendering, part volume extraction, key-slice mask interpolation, local-axis reslicing, morphology segmentation, internal morphology, ant taxonomy, Formicidae, biodiversity informatics, Agent Center

## Citation

If TaxaMask helps your research, please cite the software release:

```text
TaxaMask: a taxonomy-oriented morphology annotation, evidence review, and dataset workbench.
Zenodo DOI (all versions): https://doi.org/10.5281/zenodo.20619867
```

## License

TaxaMask source code is licensed under the GNU Affero General Public License v3.0. Commercial use is allowed under the license, but modified versions and network services must comply with AGPLv3 source-disclosure obligations. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

The bundled Ant-Code Agent Center under `vendor/ant-code/` is first-party TaxaMask source code. The directory name is retained for runtime layout compatibility; it should not be interpreted as a third-party dependency or excluded from attribution for the TaxaMask project.
