import os
import subprocess
import sys
from pathlib import Path


def open_path(path, platform: str | None = None, runner=None):
    if path is None:
        return False
    target = str(Path(path))
    if not target or not os.path.exists(target):
        return False

    active_platform = (platform or sys.platform).lower()
    run = runner or subprocess.run

    if active_platform.startswith("win"):
        os.startfile(target)
        return True
    if active_platform == "darwin":
        run(["open", target], check=False)
        return True

    run(["xdg-open", target], check=False)
    return True
