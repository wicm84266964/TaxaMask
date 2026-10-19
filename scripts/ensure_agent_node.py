#!/usr/bin/env python
"""Place a Node.js 22.18+ runtime in the active Python environment.

TaxaMask looks for node.exe beside the Python that launches the GUI before it
looks at PATH. A machine-wide Node 22.14 install is not new enough for the
embedded Agent Center, and a missing qualified Node can make Windows fall back
to WSL. This script makes a new install self-contained.
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

NODE_DIST_VERSION = "22.22.2"
MIN_MAJOR = 22
MIN_MINOR = 18


def python_prefix(executable: str | None = None) -> Path:
    """Use the environment of the Python that is running, not another shell's CONDA_PREFIX."""
    exe = Path(executable or sys.executable).resolve()
    if exe.parent.name.lower() == "scripts":
        return exe.parent.parent
    if exe.parent.name == "bin" and (exe.parent.parent / "conda-meta").exists():
        return exe.parent.parent
    return exe.parent


def installed_node_path(prefix: Path) -> Path:
    if platform.system() == "Windows":
        return prefix / "node.exe"
    return prefix / "bin" / "node"


def node_version(node_path: Path) -> tuple[int, int, int] | None:
    if not node_path.is_file():
        return None
    try:
        completed = subprocess.run(
            [str(node_path), "-p", "process.versions.node"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    parts = completed.stdout.strip().split(".")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return int(parts[0]), int(parts[1]), patch


def node_is_qualified(node_path: Path) -> bool:
    version = node_version(node_path)
    if version is None:
        return False
    major, minor, _patch = version
    return major > MIN_MAJOR or (major == MIN_MAJOR and minor >= MIN_MINOR)


def candidate_nodes() -> list[Path]:
    names = ("node.exe", "node") if platform.system() == "Windows" else ("node",)
    found: list[Path] = []
    explicit = os.environ.get("TAXAMASK_NODE_EXE", "").strip()
    if explicit:
        found.append(Path(explicit))
    for command in names:
        located = shutil.which(command)
        if located:
            found.append(Path(located))
    if platform.system() == "Windows":
        for folder in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs"),
        ):
            if folder:
                found.append(Path(folder) / "node.exe")
    unique: list[Path] = []
    seen = set()
    for path in found:
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _copy_windows_runtime(source: Path, prefix: Path) -> Path:
    destination_dir = prefix / "taxamask-node"
    destination_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination_dir / "node.exe")
    source_dir = source.parent
    for name in ("npm", "npm.cmd", "npm.ps1", "npx", "npx.cmd", "npx.ps1"):
        item = source_dir / name
        if item.is_file():
            shutil.copy2(item, destination_dir / name)
    npm_modules = source_dir / "node_modules" / "npm"
    if npm_modules.is_dir():
        target = destination_dir / "node_modules" / "npm"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(npm_modules, target)
    installed = prefix / "node.exe"
    shutil.copy2(destination_dir / "node.exe", installed)
    return installed


def _copy_unix_runtime(source: Path, prefix: Path) -> Path:
    destination = prefix / "bin" / "node"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        destination.symlink_to(source.resolve())
    except OSError:
        shutil.copy2(source, destination)
        destination.chmod(0o755)
    return destination


def install_node_from_path(source: Path, prefix: Path) -> Path:
    if platform.system() == "Windows":
        return _copy_windows_runtime(source, prefix)
    return _copy_unix_runtime(source, prefix)


def dist_archive_name(system: str, machine: str, version: str = NODE_DIST_VERSION) -> str:
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine.lower())
    if arch is None:
        raise RuntimeError(f"Unsupported CPU architecture for Agent Center Node.js: {machine}")
    system = system.lower()
    if system == "windows":
        if arch != "x64":
            raise RuntimeError("The Windows Agent Center Node.js package is prepared for 64-bit x64.")
        return f"node-v{version}-win-x64.zip"
    if system == "linux":
        return f"node-v{version}-linux-{arch}.tar.xz"
    if system == "darwin":
        return f"node-v{version}-darwin-{arch}.tar.gz"
    raise RuntimeError(f"Unsupported operating system for Agent Center Node.js: {system}")


def download_node_archive(version: str = NODE_DIST_VERSION) -> bytes:
    name = dist_archive_name(platform.system(), platform.machine(), version)
    url = f"https://nodejs.org/dist/v{version}/{name}"
    print(f"Downloading Node.js {version} from {url}")
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def install_node_from_archive(archive: bytes, prefix: Path, system: str | None = None) -> Path:
    system = (system or platform.system()).lower()
    if system == "windows":
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            member = next(item for item in bundle.namelist() if item.endswith("/node.exe") or item.endswith("node.exe"))
            source_root = member.split("/")[0]
            destination_dir = prefix / "taxamask-node"
            if destination_dir.exists():
                shutil.rmtree(destination_dir)
            destination_dir.mkdir(parents=True)
            for item in bundle.namelist():
                if not item.startswith(source_root + "/"):
                    continue
                relative = item[len(source_root) + 1 :]
                if not relative or relative.endswith("/"):
                    continue
                if not (
                    relative in {"node.exe", "npm", "npm.cmd", "npm.ps1", "npx", "npx.cmd", "npx.ps1"}
                    or relative.startswith("node_modules/npm/")
                ):
                    continue
                target = destination_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(bundle.read(item))
        installed = prefix / "node.exe"
        shutil.copy2(destination_dir / "node.exe", installed)
        return installed
    suffix = ".tar.xz" if archive[:6] == b"\xfd7zXZ\x00" else ".tar.gz"
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / f"node{suffix}"
        archive_path.write_bytes(archive)
        with tarfile.open(archive_path) as bundle:
            bundle.extractall(temp_dir)
        extracted = next(Path(temp_dir).glob("node-v*"))
        return _copy_unix_runtime(extracted / "bin" / "node", prefix)


def ensure_agent_node(prefix: Path | None = None, download: bool = True) -> Path:
    prefix = (prefix or python_prefix()).resolve()
    installed = installed_node_path(prefix)
    if node_is_qualified(installed):
        print(f"Agent Center Node.js is ready: {installed}")
        return installed
    for candidate in candidate_nodes():
        if node_is_qualified(candidate):
            installed = install_node_from_path(candidate, prefix)
            print(f"Copied Node.js into the Python environment: {installed}")
            return installed
    if not download:
        raise RuntimeError("Node.js 22.18 or newer was not found, and download is disabled.")
    archive = download_node_archive()
    installed = install_node_from_archive(archive, prefix)
    if not node_is_qualified(installed):
        raise RuntimeError(f"Installed Node.js did not pass the 22.18 check: {installed}")
    print(f"Installed Node.js into the Python environment: {installed}")
    return installed


def run_npm_ci(node_path: Path, project_root: Path) -> None:
    ant_code = project_root / "vendor" / "ant-code"
    npm = node_path.parent / "taxamask-node" / ("npm.cmd" if platform.system() == "Windows" else "npm")
    if not npm.is_file():
        sibling = node_path.parent / ("npm.cmd" if platform.system() == "Windows" else "npm")
        npm = sibling if sibling.is_file() else Path(shutil.which("npm") or "")
    if not npm.is_file():
        raise RuntimeError("npm was not found beside the prepared Node.js runtime.")
    print(f"Installing Agent Center packages with {npm}")
    subprocess.run([str(npm), "ci"], cwd=ant_code, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Node.js 22.18+ for the TaxaMask Agent Center.")
    parser.add_argument("--prefix", type=Path, default=None, help="Python environment prefix. Defaults to the active environment.")
    parser.add_argument("--no-download", action="store_true", help="Fail instead of downloading Node.js when none is installed.")
    parser.add_argument("--npm-ci", action="store_true", help="Also run npm ci in vendor/ant-code.")
    args = parser.parse_args(argv)
    try:
        node_path = ensure_agent_node(args.prefix, download=not args.no_download)
        if args.npm_ci:
            run_npm_ci(node_path, Path(__file__).resolve().parents[1])
    except Exception as exc:
        print(f"Agent Center Node.js setup failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
