#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR" || exit 1

PROJECT_ROOT="$SCRIPT_DIR"
ANT_CODE_ROOT="${TAXAMASK_ANT_CODE_ROOT:-$PROJECT_ROOT/vendor/ant-code}"
DASHBOARD_ENTRY="$ANT_CODE_ROOT/src/cli/dashboard.js"
NODE_EXE=""
PORT="${TAXAMASK_ANTCODE_PORT:-7410}"

open_dashboard_url() {
  local url="$1"
  if [[ -z "$url" || "${TAXAMASK_ANTCODE_OPEN_BROWSER:-1}" == "0" ]]; then
    return 1
  fi

  if command -v wslview >/dev/null 2>&1; then
    wslview "$url" >/dev/null 2>&1 &
    return 0
  fi

  if [[ -n "${WSL_DISTRO_NAME:-}" ]] || grep -qi "microsoft\\|wsl" /proc/version 2>/dev/null; then
    if command -v powershell.exe >/dev/null 2>&1; then
      powershell.exe -NoProfile -Command "Start-Process '$url'" >/dev/null 2>&1 &
      return 0
    fi
    if command -v cmd.exe >/dev/null 2>&1; then
      cmd.exe /c start "" "$url" >/dev/null 2>&1 &
      return 0
    fi
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
    return 0
  fi

  return 1
}

if [[ ! -f "$DASHBOARD_ENTRY" ]]; then
  echo "Cannot find the bundled Ant-Code dashboard entry:"
  echo "$DASHBOARD_ENTRY"
  echo
  echo "Make sure vendor/ant-code is included with this TaxaMask copy."
  exit 1
fi

if [[ -n "${TAXAMASK_NODE_EXE:-}" ]]; then
  if [[ -x "$TAXAMASK_NODE_EXE" ]] || command -v "$TAXAMASK_NODE_EXE" >/dev/null 2>&1; then
    NODE_EXE="$TAXAMASK_NODE_EXE"
  fi
fi

if [[ -z "$NODE_EXE" ]]; then
  for candidate in "$ANT_CODE_ROOT/node" "$PROJECT_ROOT/node"; do
    if [[ -x "$candidate" ]]; then
      NODE_EXE="$candidate"
      break
    fi
  done
fi

if [[ -z "$NODE_EXE" ]]; then
  if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    . "$HOME/.nvm/nvm.sh"
  fi
  for candidate in \
    "$HOME/.local/bin/node" \
    "$HOME/miniconda3/envs/taxamask/bin/node" \
    "$HOME/anaconda3/envs/taxamask/bin/node" \
    "$HOME/miniforge3/envs/taxamask/bin/node" \
    "$HOME/mambaforge/envs/taxamask/bin/node" \
    "$HOME/.conda/envs/taxamask/bin/node"; do
    if [[ -x "$candidate" ]]; then
      NODE_EXE="$candidate"
      break
    fi
  done
fi

if [[ -z "$NODE_EXE" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_EXE="$(command -v node)"
  fi
fi

if [[ -z "$NODE_EXE" ]]; then
  echo "Cannot find Node.js."
  echo
  echo "This recovery script does not need PySide6 or the TaxaMask GUI,"
  echo "but it does need Node.js 20 or newer to run the bundled Ant-Code dashboard."
  echo "You can also set TAXAMASK_NODE_EXE to the full path of node."
  echo
  exit 1
fi

"$NODE_EXE" -e "const major=Number(process.versions.node.split('.')[0]); process.exit(major>=20?0:1)" >/dev/null 2>&1
if [[ $? -ne 0 ]]; then
  echo "Node.js 20 or newer is required."
  echo "Current Node executable:"
  echo "$NODE_EXE"
  echo
  "$NODE_EXE" -v
  exit 1
fi

if [[ ! -d "$ANT_CODE_ROOT/node_modules" ]]; then
  echo "Ant-Code dependencies are missing:"
  echo "$ANT_CODE_ROOT/node_modules"
  echo
  echo "Run this first:"
  echo "  cd \"$ANT_CODE_ROOT\" && npm ci"
  echo
  exit 1
fi

export LAB_AGENT_PACKAGE_ROOT="$ANT_CODE_ROOT"
export LAB_AGENT_CONFIG="${TAXAMASK_ANT_CODE_CONFIG:-$PROJECT_ROOT/AntSleap/config/taxamask_ant_code.config.json}"

echo "Starting Ant-Code recovery dashboard for TaxaMask..."
echo "Project: $PROJECT_ROOT"
echo "Node: $NODE_EXE"
echo "Port: $PORT (if busy, Ant-Code will try the next available port)"
echo
echo "Keep this terminal open while using the dashboard."
echo "Press Ctrl+C to stop the local dashboard server."
echo
echo "The dashboard should open in your browser automatically."
echo

"$NODE_EXE" "$DASHBOARD_ENTRY" --project "$PROJECT_ROOT" --port "$PORT" --no-open 2>&1 | while IFS= read -r line; do
  echo "$line"
  if [[ "$line" =~ Ant[[:space:]]Code[[:space:]]Dashboard[[:space:]]running[[:space:]]at[[:space:]](http://[^[:space:]]+) ]]; then
    dashboard_url="${BASH_REMATCH[1]}"
    echo "Opening browser: $dashboard_url"
    if ! open_dashboard_url "$dashboard_url"; then
      echo "Open this URL manually: $dashboard_url"
    fi
  fi
done
status=${PIPESTATUS[0]}

if [[ $status -ne 0 ]]; then
  echo
  echo "Ant-Code dashboard exited with an error. Check the messages above."
fi

exit "$status"
