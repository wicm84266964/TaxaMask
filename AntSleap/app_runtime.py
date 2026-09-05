from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(PACKAGE_DIR)
_RUNTIME_LOG_FILE = None
_RUNTIME_LOG_PATH = ""
_RUNTIME_LOG_BYTES_WRITTEN = 0
_RUNTIME_LOG_LIMIT_REACHED = False


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


def qtwebengine_rendering_mode():
    value = os.environ.get("TAXAMASK_QTWEBENGINE_RENDERING", "").strip().lower()
    aliases = {
        "gpu": "hardware",
        "accelerated": "hardware",
        "cpu": "software",
        "safe": "software",
        "compatibility": "software",
    }
    value = aliases.get(value, value)
    if value in {"auto", "hardware", "software"}:
        return value
    if sys.platform == "linux" or is_wsl_runtime():
        return "software"
    return "auto"


def ensure_qtwebengine_quiet_cpu_flags():
    mode = qtwebengine_rendering_mode()
    if mode == "software":
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
    return mode


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


def _ensure_writable_application_config(env_name, relative_dir):
    if os.environ.get(env_name):
        return
    if not (sys.platform == "linux" or is_wsl_runtime()):
        return
    xdg_root = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_root:
        candidate = Path(xdg_root) / relative_dir
    else:
        candidate = Path.home() / ".config" / relative_dir
    if _directory_is_writable(candidate):
        return
    fallback_root = Path(REPO_ROOT) / "TaxaMask_outputs"
    # YOLO_CONFIG_DIR points to the parent directory; Ultralytics appends
    # its own "Ultralytics" subdirectory.  Other variables, such as
    # MPLCONFIGDIR, point directly at the application directory.
    fallback = fallback_root if env_name == "YOLO_CONFIG_DIR" else fallback_root / relative_dir
    if _directory_is_writable(fallback):
        os.environ[env_name] = str(fallback)


def _ensure_cjk_fontconfig_for_wsl():
    """Make CJK fonts visible to Qt when WSL has no writable user font dirs.

    WSLg often exposes Microsoft YaHei / SimSun from the Windows side even
    when the Linux side has no CJK fonts installed.  Fontconfig cannot write
    its cache below the read-only ``~/.config`` in this sandbox, so we point
    it at a repo-local cache and font directory.
    """
    if os.environ.get("FONTCONFIG_FILE"):
        return
    if not (sys.platform == "linux" and is_wsl_runtime()):
        return
    windows_font_dir = Path("/mnt/c/Windows/Fonts")
    font_names = ("msyh.ttc", "msyhbd.ttc", "simsun.ttc")
    available_sources = [windows_font_dir / name for name in font_names if (windows_font_dir / name).exists()]
    if not available_sources:
        return
    fonts_dir = Path(REPO_ROOT) / "TaxaMask_outputs" / "fonts"
    cache_dir = Path(REPO_ROOT) / "TaxaMask_outputs" / "fontconfig-cache"
    config_path = fonts_dir / "fonts.conf"
    try:
        fonts_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for source in available_sources:
            target = fonts_dir / source.name
            if target.exists() or target.is_symlink():
                continue
            try:
                target.symlink_to(source)
            except OSError:
                shutil.copyfile(source, target)
        if not config_path.exists():
            config_path.write_text(
                '<?xml version="1.0"?>\n'
                '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
                '<fontconfig>\n'
                '  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>\n'
                f'  <dir>{fonts_dir}</dir>\n'
                f'  <cachedir>{cache_dir}</cachedir>\n'
                '</fontconfig>\n',
                encoding="utf-8",
            )
        os.environ.setdefault("FONTCONFIG_FILE", str(config_path))
    except OSError:
        return


def prepare_qt_runtime_environment():
    if sys.platform == "linux" or is_wsl_runtime():
        os.environ.setdefault("TAXAMASK_QTWEBENGINE_RENDERING", "software")
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        os.environ.setdefault("TAXAMASK_ANTCODE_BROWSER_MODE", "1")
        _ensure_writable_application_config("YOLO_CONFIG_DIR", "Ultralytics")
        _ensure_writable_application_config("MPLCONFIGDIR", "matplotlib")
        _ensure_cjk_fontconfig_for_wsl()
    ensure_qtwebengine_quiet_cpu_flags()


def qt_message_should_be_ignored(message):
    text = str(message or "")
    return (
        "QWindowsWindow::setGeometry" in text
        and "Unable to set geometry" in text
    )


def install_qt_noise_filters():
    """Hide a known-harmless Windows window-manager warning.

    On 1080p displays, Qt may ask for a client size such as 560x249 while
    Windows returns 560x255 because of title-bar min-track. That prints
    QWindowsWindow::setGeometry and looks like a crash in the launch console.
    """
    if sys.platform != "win32":
        return None
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        return None

    previous = getattr(install_qt_noise_filters, "_previous", None)

    def handler(mode, context, message):
        if qt_message_should_be_ignored(message):
            return
        if previous is not None:
            previous(mode, context, message)
            return
        try:
            stream = sys.stderr
            prefix = ""
            if mode == QtMsgType.QtFatalMsg:
                prefix = "FATAL: "
            elif mode == QtMsgType.QtCriticalMsg:
                prefix = "CRITICAL: "
            stream.write(f"{prefix}{message}\n")
        except Exception:
            pass

    previous = qInstallMessageHandler(handler)
    install_qt_noise_filters._previous = previous
    install_qt_noise_filters._handler = handler
    return handler


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


def runtime_log_max_bytes():
    try:
        value = int(
            os.environ.get("TAXAMASK_RUNTIME_LOG_MAX_BYTES", str(16 * 1024 * 1024))
            or 16 * 1024 * 1024
        )
    except Exception:
        value = 16 * 1024 * 1024
    return max(1024, value)


def _write_runtime_log_text(text):
    global _RUNTIME_LOG_BYTES_WRITTEN, _RUNTIME_LOG_LIMIT_REACHED
    handle = _RUNTIME_LOG_FILE
    if handle is None or _RUNTIME_LOG_LIMIT_REACHED:
        return False
    payload = str(text)
    payload_bytes = len(payload.encode("utf-8"))
    maximum = runtime_log_max_bytes()
    if _RUNTIME_LOG_BYTES_WRITTEN + payload_bytes > maximum:
        warning = (
            f"[{runtime_log_timestamp()}] runtime_log_capacity_reached "
            f"max_bytes={maximum}\n"
        )
        warning_bytes = len(warning.encode("utf-8"))
        if _RUNTIME_LOG_BYTES_WRITTEN + warning_bytes <= maximum:
            handle.write(warning)
            handle.flush()
            _RUNTIME_LOG_BYTES_WRITTEN += warning_bytes
        _RUNTIME_LOG_LIMIT_REACHED = True
        return False
    handle.write(payload)
    handle.flush()
    _RUNTIME_LOG_BYTES_WRITTEN += payload_bytes
    return True


def setup_runtime_logging():
    global _RUNTIME_LOG_FILE, _RUNTIME_LOG_PATH
    global _RUNTIME_LOG_BYTES_WRITTEN, _RUNTIME_LOG_LIMIT_REACHED
    if _RUNTIME_LOG_FILE is not None or not runtime_log_enabled():
        return _RUNTIME_LOG_PATH
    try:
        log_dir = os.path.join(REPO_ROOT, "TaxaMask_outputs", "runtime_logs")
        os.makedirs(log_dir, exist_ok=True)
        runtime_log_prune(log_dir)
        filename = f"taxamask_runtime_{runtime_log_filename_timestamp()}_{os.getpid()}.log"
        _RUNTIME_LOG_PATH = os.path.join(log_dir, filename)
        _RUNTIME_LOG_FILE = open(_RUNTIME_LOG_PATH, "a", encoding="utf-8", buffering=1)
        _RUNTIME_LOG_BYTES_WRITTEN = 0
        _RUNTIME_LOG_LIMIT_REACHED = False
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
        _write_runtime_log_text(" ".join(parts) + "\n")
    except Exception:
        pass


def runtime_log_exception(event, exc_type, exc_value, exc_tb):
    handle = _RUNTIME_LOG_FILE
    if handle is None:
        return
    try:
        import traceback

        runtime_log_event(event, error=repr(exc_value))
        traceback_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        )
        if not str(exc_value).endswith("\n"):
            traceback_text += "\n"
        _write_runtime_log_text(traceback_text)
    except Exception:
        pass


_is_wsl_runtime = is_wsl_runtime
_append_env_flag = append_env_flag
_qtwebengine_rendering_mode = qtwebengine_rendering_mode
_ensure_qtwebengine_quiet_cpu_flags = ensure_qtwebengine_quiet_cpu_flags
_prepare_qt_runtime_environment = prepare_qt_runtime_environment
_runtime_log_enabled = runtime_log_enabled
_runtime_log_timestamp = runtime_log_timestamp
_runtime_log_filename_timestamp = runtime_log_filename_timestamp
_runtime_log_prune = runtime_log_prune
_runtime_log_max_bytes = runtime_log_max_bytes
_setup_runtime_logging = setup_runtime_logging
_runtime_log_value = runtime_log_value
