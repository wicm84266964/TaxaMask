# TaxaMask Platform Setup

TaxaMask is currently a source-based research application. The first compatibility target is not a one-click installer for every operating system; it is a reproducible source setup that lets researchers run the workbench, validate small projects, and use Linux CUDA machines for heavier training.

## Support Status

| Platform | Current role | Practical expectation |
| --- | --- | --- |
| Windows 10/11 | Primary validated desktop environment | Best current path for GUI use, annotation, PDF processing, and local CUDA training when the PyTorch build matches the machine. |
| Linux | Main cross-platform target | Intended for lab workstations, servers, CUDA training, batch processing, and headless tools. GUI use may require system Qt libraries. |
| macOS | CPU-only source trial path | Intended for lightweight annotation, project review, teaching, and small CPU smoke tests. Apple Silicon MPS is not supported in the first compatibility pass. |

## Install Order

Install prerequisites first:

- Git, or the ability to download and extract the GitHub ZIP archive.
- Conda or another Python environment manager.
- Python 3.12 for the recommended public source setup.
- Node.js 20 or newer with npm for the embedded Agent Center / Ant-Code dashboard.

Clone the source repository and enter it before installing dependencies:

```bash
git clone https://github.com/wicm84266964/TaxaMask.git
cd TaxaMask
```

Create and activate the recommended Python environment:

```bash
conda create -n taxamask python=3.12
conda activate taxamask
```

Always install a hardware-appropriate PyTorch build before installing the base requirements:

```bash
pip install -r requirements-torch-cpu.txt
pip install -r requirements.txt
```

For matching NVIDIA CUDA 12.1 environments:

```bash
pip install -r requirements-torch-cu121.txt
pip install -r requirements.txt
```

Linux CUDA users should check the official PyTorch install command for the installed NVIDIA driver and CUDA runtime. The CUDA 12.1 file is an example, not a promise that every CUDA workstation should use that exact wheel.

macOS users should not install the CUDA requirements file. Use a CPU-compatible PyTorch installation for this first compatibility target. Advanced users may experiment with their own PyTorch/SAM stack, but MPS acceleration is not a supported TaxaMask runtime device yet.

Install the bundled Agent Center dependencies after cloning:

```bash
cd vendor/ant-code
npm ci
cd ../..
```

The source release does not include `node_modules`. Without this step, the main Python GUI may still open, but the embedded Agent Center, browser dashboard, and `启动AntCode修复面板.bat` recovery panel cannot be expected to work.

TaxaMask can launch without API keys, and the Agent Center dashboard can open before a model is configured. Model-backed Agent Center chat, VLM drafts, and external model routes require local gateway or API settings supplied by the user environment. Do not commit real keys, private gateway URLs, or runtime settings.

If the PySide6 GUI cannot start after source changes, launch the bundled dashboard directly from the repository root:

```bash
node vendor/ant-code/src/cli/dashboard.js --project . --port 7410
```

On Windows, `启动AntCode修复面板.bat` provides the same recovery route with additional Node.js discovery. On Ubuntu/Linux or from a WSL shell, use:

```bash
bash ./启动TaxaMask.sh
bash ./启动AntCode修复面板.sh
```

When the TaxaMask GUI itself is a Windows Python process but Ant-Code was installed in WSL Ubuntu, enable the WSL runtime bridge before starting the GUI:

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

`TAXAMASK_WSL_DISTRO` is optional when the default WSL distribution is the right one. Set `TAXAMASK_WSL_PROJECT_DIR`, `TAXAMASK_WSL_ANT_CODE_ROOT`, or `TAXAMASK_WSL_ANT_CODE_CONFIG` only when the automatic `wslpath` conversion does not point at the Linux-side checkout that contains `vendor/ant-code/node_modules`.

## Poppler for PDF Processing

Some PDF image fallback paths depend on Poppler through `pdf2image`. PyMuPDF-based figure extraction can still be useful without every optional fallback, but missing Poppler should be treated as a setup issue rather than an API or model failure.

- Windows: install a Poppler for Windows build and add its `bin` directory to `PATH`, or place the local bundle under `external_tools/poppler`.
- Ubuntu/Debian: `sudo apt install poppler-utils`
- Fedora/RHEL: `sudo dnf install poppler-utils`
- macOS: `brew install poppler`

## Linux GUI Notes

PySide6 may need system display libraries on minimal Linux installations. On Ubuntu-like systems, common missing pieces include XCB, OpenGL, and xkbcommon libraries. Headless test runs should use:

```bash
QT_QPA_PLATFORM=offscreen
```

This is useful for CI and smoke tests, but normal interactive annotation still needs a working desktop/session display.

The repository includes a lightweight GitHub Actions smoke workflow for Windows, Linux, and macOS. It is intentionally limited to configuration, path helpers, window construction, and other non-training checks so CI does not require model weights or research data.

## Runtime Device Policy

TaxaMask currently exposes:

- `Auto (CUDA if available)`
- `CPU only`
- `CUDA GPU`

`Auto` selects CUDA when PyTorch reports CUDA is available; otherwise it uses CPU. It does not automatically select Apple Silicon MPS.

For research work, CPU mode is best understood as an installation and small-project validation path. Large Locator/SAM/Blink training should still be planned on an NVIDIA CUDA workstation, especially for high-resolution images or larger Blink input sizes.

## Moving Projects Between Machines

Project JSON files store image paths so labels, boxes, scales, and provenance stay attached to the right specimen image. When a project is moved from Windows to Linux/macOS, or when an image library is moved to another disk, use the GUI path-health tool before training:

1. Open the project.
2. Choose `File -> Check / Relocate Project Images`.
3. Review the available/missing image count.
4. If images are missing, choose the new image-library root.
5. Apply the preview only if the listed old/new matches are correct.
6. Save the project after the remap.

The remap preview only updates paths that are missing in the current project and have a unique filename match under the selected root. Duplicate filenames are left unresolved so a specimen image is not silently connected to the wrong label record.

## User Configuration Location

TaxaMask stores local runtime preferences outside the repository so they are not accidentally committed with research data or API settings.

- Windows: `%APPDATA%/TaxaMask/user_config.json`
- Linux: `~/.config/taxamask/user_config.json`, or `$XDG_CONFIG_HOME/taxamask/user_config.json` when `XDG_CONFIG_HOME` is set
- macOS: `~/Library/Application Support/TaxaMask/user_config.json`

If an old repository-root `user_config.json` is found on first run, TaxaMask copies it to the platform-specific location and leaves the old file in place. This preserves existing settings while moving new writes to the safer user configuration directory.

## External Backends

External backend commands are interpreted by the current operating system shell. Keep paths with spaces quoted, and always include one of these placeholders:

- `{contract}`
- `{contract_json}`

The contract JSON is the cross-platform boundary. The command syntax around it remains platform-specific so advanced users can call their own Python, shell, or batch scripts directly.

## Validation Matrix

The repository smoke workflow is intentionally lightweight. It verifies that the source tree, platform path helpers, configuration migration, basic GUI construction, and cross-platform opening helpers work without model weights or research data.

| Target | Minimum smoke checks | Manual checks before real research use |
| --- | --- | --- |
| Windows 10/11 CPU | Unit tests, GUI smoke, config path migration, project open/save, PDF dependency status display | Open a real project, verify image paths, run a tiny PDF batch, confirm SAM weights path if using assisted annotation. |
| Windows 10/11 CUDA | Windows CPU checks plus `Auto` resolving to CUDA when PyTorch sees the GPU | Train a tiny Locator/SAM/Blink run before production, confirm CUDA PyTorch matches the driver. |
| Ubuntu/Linux CPU | Unit tests under `QT_QPA_PLATFORM=offscreen`, GUI construction, platform config path, Poppler from `poppler-utils` | Launch the GUI in the actual desktop/session environment, relocate a copied project, run a tiny annotation/export workflow. |
| Ubuntu/Linux CUDA | Linux CPU checks plus CUDA PyTorch chosen for the installed driver/runtime | Run a tiny training and batch inference cycle on the target workstation or server. |
| macOS CPU | CPU install, config path, GUI smoke where PySide6 system libraries allow it, project open/save | Treat as a light source trial: inspect projects, annotate small batches, avoid large training expectations. |
| macOS MPS | Not a first-pass target | Do not treat MPS as supported until SAM, torchvision, Ultralytics, and training paths are validated on real Mac hardware. |

For local maintainer validation, the suggested conda environment name is `taxamask`. It is only a convenient environment label, not a requirement baked into the program.
