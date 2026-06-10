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
