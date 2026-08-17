import os
import sys
from pathlib import Path


APP_NAME = "TaxaMask"
LINUX_APP_DIR = "taxamask"
CONFIG_FILENAME = "user_config.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def legacy_repo_config_path() -> Path:
    return repo_root() / CONFIG_FILENAME


def user_config_dir(platform: str | None = None, env: dict[str, str] | None = None, home: str | Path | None = None) -> Path:
    active_platform = (platform or sys.platform).lower()
    active_env = env if env is not None else os.environ
    home_dir = Path(home) if home is not None else Path.home()

    if active_platform.startswith("win"):
        appdata = str(active_env.get("APPDATA", "") or "").strip()
        if appdata:
            return Path(appdata) / APP_NAME
        return home_dir / "AppData" / "Roaming" / APP_NAME

    if active_platform == "darwin":
        return home_dir / "Library" / "Application Support" / APP_NAME

    xdg_config_home = str(active_env.get("XDG_CONFIG_HOME", "") or "").strip()
    if xdg_config_home:
        return Path(xdg_config_home) / LINUX_APP_DIR
    return home_dir / ".config" / LINUX_APP_DIR


def user_config_path(platform: str | None = None, env: dict[str, str] | None = None, home: str | Path | None = None) -> Path:
    return user_config_dir(platform=platform, env=env, home=home) / CONFIG_FILENAME


def _directory_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    probe = path / f".taxamask_write_probe_{os.getpid()}"
    try:
        descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def writable_user_config_dir(platform: str | None = None, env: dict[str, str] | None = None, home: str | Path | None = None) -> Path:
    """Return the standard user config dir when writable, otherwise a repo-local fallback.

    Some sandboxed WSL/container environments expose ``~/.config`` as read-only
    even when its POSIX mode suggests otherwise.  TaxaMask already keeps runtime
    artifacts below ``TaxaMask_outputs/`` in the repository, so the fallback keeps
    user configuration on the same writable volume.
    """
    candidate = user_config_dir(platform=platform, env=env, home=home)
    if _directory_is_writable(candidate):
        return candidate
    fallback = repo_root() / "TaxaMask_outputs" / "config"
    _directory_is_writable(fallback)
    return fallback


def writable_user_config_path(platform: str | None = None, env: dict[str, str] | None = None, home: str | Path | None = None) -> Path:
    return writable_user_config_dir(platform=platform, env=env, home=home) / CONFIG_FILENAME
