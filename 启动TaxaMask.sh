#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR" || exit 1

PYTHON_EXE=""
PYTHON_SOURCE=""

try_python() {
  local candidate="$1"
  local source="$2"
  local strict="${3:-0}"
  if [[ -z "$candidate" ]]; then
    return 1
  fi
  if ! command -v "$candidate" >/dev/null 2>&1 && [[ ! -x "$candidate" ]]; then
    return 1
  fi
  "$candidate" -c "import PySide6, numpy, cv2, PIL, matplotlib, requests; import fitz, pdfplumber" >/dev/null 2>&1
  if [[ $? -ne 0 ]]; then
    if [[ "$strict" == "1" ]]; then
      echo "Selected Python is missing one or more minimum TaxaMask dependencies:"
      echo "$candidate"
    else
      echo "Skipping Python without minimum TaxaMask dependencies: $candidate"
    fi
    return 1
  fi
  PYTHON_EXE="$candidate"
  PYTHON_SOURCE="$source"
  return 0
}

if [[ -n "${TAXAMASK_PYTHON_EXE:-}" ]]; then
  if ! try_python "$TAXAMASK_PYTHON_EXE" "TAXAMASK_PYTHON_EXE" 1; then
    echo
    exit 1
  fi
fi

if [[ -z "$PYTHON_EXE" ]]; then
  for candidate in \
    "$SCRIPT_DIR/.venv/bin/python" \
    "$SCRIPT_DIR/venv/bin/python" \
    "$SCRIPT_DIR/env/bin/python" \
    "${CONDA_PREFIX:-}/bin/python" \
    "$HOME/miniconda3/envs/taxamask/bin/python" \
    "$HOME/anaconda3/envs/taxamask/bin/python" \
    "$HOME/miniforge3/envs/taxamask/bin/python" \
    "$HOME/mambaforge/envs/taxamask/bin/python" \
    "$HOME/.conda/envs/taxamask/bin/python"; do
    if try_python "$candidate" "known environment path"; then
      break
    fi
  done
fi

if [[ -z "$PYTHON_EXE" ]]; then
  for command_name in python3 python; do
    if try_python "$command_name" "PATH $command_name"; then
      break
    fi
  done
fi

if [[ -z "$PYTHON_EXE" ]]; then
  echo "Cannot find a Python environment with the minimum TaxaMask dependencies."
  echo
  echo "Recommended options:"
  echo "  1. Activate your Conda environment first, then run: bash ./启动TaxaMask.sh"
  echo "  2. Set TAXAMASK_PYTHON_EXE to the full path of that environment's python."
  echo "  3. Create a local .venv or a Conda environment named taxamask."
  echo "  4. Run python AntSleap/main.py from an already configured terminal."
  echo
  exit 1
fi

export QT_OPENGL="${QT_OPENGL:-software}"
export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export TAXAMASK_ANTCODE_BROWSER_MODE="${TAXAMASK_ANTCODE_BROWSER_MODE:-1}"
export TAXAMASK_ENABLE_TIF_WORKFLOW="${TAXAMASK_ENABLE_TIF_WORKFLOW:-1}"
export __NV_PRIME_RENDER_OFFLOAD="${__NV_PRIME_RENDER_OFFLOAD:-0}"
if [[ " ${QTWEBENGINE_CHROMIUM_FLAGS:-} " != *" --disable-gpu-compositing "* ]]; then
  export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --disable-gpu-compositing"
fi
if [[ " ${QTWEBENGINE_CHROMIUM_FLAGS:-} " != *" --disable-gpu "* ]]; then
  export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --disable-gpu"
fi

echo "Starting TaxaMask with:"
echo "$PYTHON_EXE"
if [[ -n "$PYTHON_SOURCE" ]]; then
  echo "Source: $PYTHON_SOURCE"
fi
echo

"$PYTHON_EXE" AntSleap/main.py
status=$?

if [[ $status -ne 0 ]]; then
  echo
  echo "TaxaMask exited with an error. Check the messages above."
  echo "If the GUI cannot start after source-code changes, run:"
  echo "  bash ./启动AntCode修复面板.sh"
fi

exit "$status"
