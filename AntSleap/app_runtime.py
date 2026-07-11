from __future__ import annotations

import os
import sys


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
_RUNTIME_LOG_FILE = None
_RUNTIME_LOG_PATH = ""


def is_wsl_runtime():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def append_env_flag(name, flag):
    current = os.environ.get(name, "")
    flags = current.split()
    if flag not in flags:
        flags.append(flag)
        os.environ[name] = " ".join(flags)


def ensure_qtwebengine_quiet_cpu_flags():
    for flag in (
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-accelerated-2d-canvas",
        "--disable-es3-gl-context",
        "--disable-es3-apis",
        "--disable-webgl",
        "--disable-3d-apis",
    ):
        append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", flag)
    verbose = os.environ.get("TAXAMASK_QTWEBENGINE_VERBOSE", "").strip().lower()
    if verbose not in {"1", "true", "yes", "on", "verbose", "debug"}:
        append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging")
        append_env_flag("QTWEBENGINE_CHROMIUM_FLAGS", "--log-level=3")


def prepare_qt_runtime_environment():
    ensure_qtwebengine_quiet_cpu_flags()
    if sys.platform == "linux" or is_wsl_runtime():
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        os.environ.setdefault("TAXAMASK_ANTCODE_BROWSER_MODE", "1")


def runtime_log_enabled():
    return str(os.environ.get("TAXAMASK_RUNTIME_LOG", "1")).strip().lower() not in {"0", "false", "no", "off"}


def runtime_log_timestamp():
    import time

    return time.strftime("%Y-%m-%d %H:%M:%S")


def runtime_log_filename_timestamp():
    import time

    return time.strftime("%Y%m%d_%H%M%S")


def runtime_log_prune(log_dir):
    try:
        keep = int(os.environ.get("TAXAMASK_RUNTIME_LOG_KEEP", "20") or 20)
    except Exception:
        keep = 20
    keep = max(1, keep)
    try:
        entries = [
            os.path.join(log_dir, name)
            for name in os.listdir(log_dir)
            if name.startswith("taxamask_runtime_") and name.endswith(".log")
        ]
        entries.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        for old_path in entries[keep:]:
            try:
                os.remove(old_path)
            except OSError:
                pass
    except OSError:
        pass


def setup_runtime_logging():
    global _RUNTIME_LOG_FILE, _RUNTIME_LOG_PATH
    if _RUNTIME_LOG_FILE is not None or not runtime_log_enabled():
        return _RUNTIME_LOG_PATH
    try:
        log_dir = os.path.join(REPO_ROOT, "TaxaMask_outputs", "runtime_logs")
        os.makedirs(log_dir, exist_ok=True)
        runtime_log_prune(log_dir)
        filename = f"taxamask_runtime_{runtime_log_filename_timestamp()}_{os.getpid()}.log"
        _RUNTIME_LOG_PATH = os.path.join(log_dir, filename)
        _RUNTIME_LOG_FILE = open(_RUNTIME_LOG_PATH, "a", encoding="utf-8", buffering=1)
        try:
            import faulthandler

            faulthandler.enable(file=_RUNTIME_LOG_FILE, all_threads=True)
        except Exception:
            pass
        runtime_log_event("startup", python=sys.executable, cwd=os.getcwd(), pid=os.getpid())
        runtime_log_prune(log_dir)
    except Exception:
        _RUNTIME_LOG_FILE = None
        _RUNTIME_LOG_PATH = ""
    return _RUNTIME_LOG_PATH


def runtime_log_value(value, limit=500):
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        text = text[:limit] + "...<truncated>"
    return text


def runtime_log_event(event, **fields):
    handle = _RUNTIME_LOG_FILE
    if handle is None:
        return
    try:
        parts = [f"[{runtime_log_timestamp()}]", runtime_log_value(event, 80)]
        for key in sorted(fields):
            value = fields.get(key)
            if value is not None:
                parts.append(f"{key}={runtime_log_value(value)}")
        handle.write(" ".join(parts) + "\n")
        handle.flush()
    except Exception:
        pass


def runtime_log_exception(event, exc_type, exc_value, exc_tb):
    handle = _RUNTIME_LOG_FILE
    if handle is None:
        return
    try:
        import traceback

        runtime_log_event(event, error=repr(exc_value))
        handle.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        if not str(exc_value).endswith("\n"):
            handle.write("\n")
        handle.flush()
    except Exception:
        pass


_is_wsl_runtime = is_wsl_runtime
_append_env_flag = append_env_flag
_ensure_qtwebengine_quiet_cpu_flags = ensure_qtwebengine_quiet_cpu_flags
_prepare_qt_runtime_environment = prepare_qt_runtime_environment
_runtime_log_enabled = runtime_log_enabled
_runtime_log_timestamp = runtime_log_timestamp
_runtime_log_filename_timestamp = runtime_log_filename_timestamp
_runtime_log_prune = runtime_log_prune
_setup_runtime_logging = setup_runtime_logging
_runtime_log_value = runtime_log_value
