import os
import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def _is_wsl_runtime():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r", encoding="utf-8", errors="ignore") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def _ensure_qtwebengine_cpu_compositing():
    flags_to_append = [
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-accelerated-2d-canvas",
        "--disable-es3-gl-context",
        "--disable-es3-apis",
        "--disable-webgl",
        "--disable-3d-apis",
    ]
    verbose = os.environ.get("TAXAMASK_QTWEBENGINE_VERBOSE", "").strip().lower()
    if verbose not in {"1", "true", "yes", "on", "verbose", "debug"}:
        flags_to_append.extend(["--disable-logging", "--log-level=3"])
    for flag in flags_to_append:
        current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        flags = current.split()
        if flag not in flags:
            flags.append(flag)
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


_ensure_qtwebengine_cpu_compositing()

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .style import get_theme_config, normalize_theme


def _env_requests_browser_mode():
    value = os.environ.get("TAXAMASK_ANTCODE_BROWSER_MODE", "").strip().lower()
    return value in {"1", "true", "yes", "on", "browser", "external"}


def _should_import_qtwebengine():
    if _env_requests_browser_mode() or _is_wsl_runtime():
        return False
    return True


QWebEngineView = None
QWebEnginePage = None
QWebEngineProfile = None
QWebEngineScript = None
TaxaMaskAgentWebPage = None
_QTWEBENGINE_IMPORT_ATTEMPTED = False
_QTWEBENGINE_IMPORT_ERROR = None


def _load_qtwebengine_classes():
    global QWebEngineView, QWebEnginePage, QWebEngineProfile, QWebEngineScript
    global _QTWEBENGINE_IMPORT_ATTEMPTED, _QTWEBENGINE_IMPORT_ERROR

    if not _should_import_qtwebengine():
        return False
    if _QTWEBENGINE_IMPORT_ATTEMPTED:
        return QWebEngineView is not None

    _QTWEBENGINE_IMPORT_ATTEMPTED = True
    _QTWEBENGINE_IMPORT_ERROR = None
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView as ImportedWebEngineView
    except Exception as exc:  # pragma: no cover - depends on local Qt installation
        QWebEngineView = None
        _QTWEBENGINE_IMPORT_ERROR = exc
        return False

    QWebEngineView = ImportedWebEngineView
    try:
        from PySide6.QtWebEngineCore import (
            QWebEnginePage as ImportedWebEnginePage,
            QWebEngineProfile as ImportedWebEngineProfile,
            QWebEngineScript as ImportedWebEngineScript,
        )
    except Exception as exc:  # pragma: no cover - depends on local Qt installation
        QWebEnginePage = None
        QWebEngineProfile = None
        QWebEngineScript = None
        _QTWEBENGINE_IMPORT_ERROR = exc
    else:
        QWebEnginePage = ImportedWebEnginePage
        QWebEngineProfile = ImportedWebEngineProfile
        QWebEngineScript = ImportedWebEngineScript
    return QWebEngineView is not None


AGENT_TRANSLATIONS = {
    "zh": {
        "TaxaMask Agent": "TaxaMask Agent",
        "Ant-Code embedded": "Ant-Code 内嵌",
        "Start Ant-Code": "启动 Ant-Code",
        "Open in browser": "浏览器打开",
        "Stop": "停止",
        "Starting Ant-Code Dashboard...": "正在启动 Ant-Code Dashboard...",
        "Ant-Code Dashboard is ready.": "Ant-Code Dashboard 已就绪。",
        "Ant-Code Dashboard is not running.": "Ant-Code Dashboard 尚未启动。",
        "Qt WebEngine is unavailable in this environment. Start Ant-Code and open it in a browser.": "当前环境缺少 Qt WebEngine。可以启动 Ant-Code 后在浏览器中打开。",
        "Ant-Code process exited.": "Ant-Code 进程已退出。",
        "Unable to start Ant-Code: {0}": "无法启动 Ant-Code：{0}",
        "Workspace permission is the default for this embedded TaxaMask agent.": "TaxaMask 内嵌 Agent 默认使用工作区权限。",
        "Agent context copied to clipboard. Paste it into the browser prompt.": "Agent 上下文已复制到剪贴板，请粘贴到浏览器里的 Ant-Code 输入框。",
        "Ant-Code executable": "Ant-Code 可执行文件",
        "not found": "未找到",
        "Project": "项目",
        "Status": "状态",
    }
}


def at(text, lang="en"):
    if lang == "zh":
        return AGENT_TRANSLATIONS["zh"].get(text, text)
    return text


def find_free_port(start=7410, host="127.0.0.1"):
    for port in range(int(start), 65535):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError("No available local port for Ant-Code Dashboard")


def _ensure_agent_web_page_class():
    global TaxaMaskAgentWebPage
    if TaxaMaskAgentWebPage is not None:
        return TaxaMaskAgentWebPage
    if QWebEnginePage is None:
        return None

    class _TaxaMaskAgentWebPage(QWebEnginePage):
        def __init__(self, panel, profile=None, parent=None):
            if profile is not None:
                super().__init__(profile, parent)
            else:
                super().__init__(parent)
            self._panel = panel

        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            try:
                self._panel._on_web_console_message(level, message, lineNumber, sourceID)
            except Exception:
                return

    TaxaMaskAgentWebPage = _TaxaMaskAgentWebPage
    return TaxaMaskAgentWebPage


class TaxaMaskAgentPanel(QWidget):
    """Embed the real Ant-Code Dashboard inside TaxaMask."""

    status_changed = Signal(str)

    def __init__(self, lang="en", parent=None, workspace_dir=None, ant_code_executable=None, ant_code_root=None):
        super().__init__(parent)
        _ = ant_code_executable
        self.lang = lang
        self.workspace_dir = os.path.abspath(str(workspace_dir or Path(__file__).resolve().parents[2]))
        self.ant_code_root = os.path.abspath(str(ant_code_root or os.environ.get("TAXAMASK_ANT_CODE_ROOT") or self._default_ant_code_root()))
        self.ant_code_config_path = os.path.abspath(str(os.environ.get("TAXAMASK_ANT_CODE_CONFIG") or self._default_ant_code_config_path()))
        self._ant_code_runtime_preference = self._read_ant_code_runtime_preference()
        self.ant_code_runtime = self._resolve_ant_code_runtime()
        self.wsl_distribution = self._resolve_wsl_distribution()
        self.wsl_executable = self._resolve_wsl_executable()
        self.node_executable = self._resolve_node_executable()
        self.ant_code_dashboard_entry = self._resolve_ant_code_dashboard_entry()
        if self._should_auto_promote_to_wsl():
            self.ant_code_runtime = "wsl"
            self.node_executable = self._resolve_node_executable()
        self.process = None
        self.dashboard_url = ""
        self.port = None
        self._context = {}
        self._health_checks_remaining = 0
        self._pending_context_prompt = ""
        self._project_display = self.workspace_dir
        self._status_text = ""
        self._load_retries = 0
        self._pending_prompt_attempts = 0
        self._preflight_checks_remaining = 0
        self._preflight_error = ""
        self._last_console_error = ""
        self._embedded_page_error = ""
        self._web_profile = None
        self._web_profile_storage_dir = ""
        self._json_health_error = ""
        self._json_health_warning = ""
        self._dashboard_log_path = ""
        self._dashboard_log_handle = None
        self._browser_context_copied = False
        self.current_theme = normalize_theme(getattr(parent, "current_theme", "dark"))
        self.browser_mode = self._resolve_browser_mode()
        self._browser_opened_for_url = ""
        self.setObjectName("taxamaskAgentPanel")
        self.setMinimumWidth(640)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()
        self._apply_style()
        self.set_language(lang)

    def _resolve_browser_mode(self):
        value = os.environ.get("TAXAMASK_ANTCODE_BROWSER_MODE", "").strip().lower()
        if value in {"0", "false", "no", "off", "embed"}:
            return False
        if value in {"1", "true", "yes", "on", "browser", "external"}:
            return True
        return sys.platform == "linux" or _is_wsl_runtime()

    def _default_ant_code_root(self):
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "vendor" / "ant-code"

    def _default_ant_code_config_path(self):
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "AntSleap" / "config" / "taxamask_ant_code.config.json"

    def _read_ant_code_runtime_preference(self):
        value = os.environ.get("TAXAMASK_ANTCODE_RUNTIME", "auto").strip().lower()
        if value in {"wsl", "wsl2", "ubuntu"}:
            return "wsl"
        if value in {"native", "local", "windows"}:
            return "native"
        return "auto"

    def _resolve_ant_code_runtime(self):
        if sys.platform != "win32":
            return "native"
        if self._ant_code_runtime_preference == "wsl":
            return "wsl"
        if self._ant_code_runtime_preference == "native":
            return "native"
        if os.environ.get("TAXAMASK_WSL_DISTRO"):
            return "wsl"
        return "native"

    def _resolve_wsl_distribution(self):
        return os.environ.get("TAXAMASK_WSL_DISTRO", "").strip()

    def _resolve_wsl_executable(self):
        if sys.platform != "win32":
            return None
        env_path = os.environ.get("TAXAMASK_WSL_EXE", "").strip()
        if env_path and Path(env_path).expanduser().exists():
            return str(Path(env_path).expanduser().resolve())
        found = shutil.which("wsl.exe") or shutil.which("wsl")
        if found:
            return found
        system_wsl = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wsl.exe"
        if system_wsl.exists():
            return str(system_wsl)
        return None

    def _resolve_node_executable(self):
        if self.ant_code_runtime == "wsl":
            return os.environ.get("TAXAMASK_WSL_NODE_EXE", "").strip() or "node"
        env_path = os.environ.get("TAXAMASK_NODE_EXE")
        if env_path and Path(env_path).expanduser().exists():
            return str(Path(env_path).expanduser().resolve())
        for candidate in self._node_executable_candidates():
            if candidate.exists():
                return str(candidate.resolve())
        for command in ("node.exe", "node"):
            found = shutil.which(command)
            if found:
                return found
        return None

    def _node_executable_candidates(self):
        names = ("node.exe", "node") if sys.platform == "win32" else ("node",)
        roots = [
            Path(self.ant_code_root),
            Path(self.workspace_dir),
        ]
        home = None
        if sys.platform != "win32":
            try:
                home = Path.home()
            except RuntimeError:
                home = None
            if home is not None:
                roots.extend([
                    home / ".local",
                    home / ".nvm" / "versions" / "node",
                    home / "miniconda3" / "envs" / "taxamask",
                    home / "anaconda3" / "envs" / "taxamask",
                    home / "miniforge3" / "envs" / "taxamask",
                    home / "mambaforge" / "envs" / "taxamask",
                    home / ".conda" / "envs" / "taxamask",
                ])
        for root in roots:
            for name in names:
                yield root / "bin" / name
                yield root / name
        if sys.platform != "win32" and home is not None:
            for candidate in sorted((home / ".nvm" / "versions" / "node").glob("*/bin/node"), reverse=True):
                yield candidate

    def _resolve_ant_code_dashboard_entry(self):
        for candidate in (
            Path(self.ant_code_root) / "src" / "cli" / "dashboard.js",
            Path(self.ant_code_root) / "src" / "cli" / "index.js",
        ):
            if candidate.exists():
                return str(candidate.resolve())
        return None

    def _should_auto_promote_to_wsl(self):
        return bool(
            sys.platform == "win32"
            and self._ant_code_runtime_preference == "auto"
            and not self.node_executable
            and self.wsl_executable
        )

    def _can_use_source_dashboard(self):
        if self.ant_code_runtime == "wsl":
            return bool(
                self.wsl_executable
                and self.ant_code_dashboard_entry
                and Path(self.ant_code_dashboard_entry).exists()
            )
        return bool(
            self.node_executable
            and Path(self.node_executable).exists()
            and self.ant_code_dashboard_entry
            and Path(self.ant_code_dashboard_entry).exists()
        )

    def _dashboard_command(self):
        if not self._can_use_source_dashboard():
            raise FileNotFoundError(
                "Ant-Code source dashboard is unavailable. Ensure Node.js is installed and "
                "vendor/ant-code/src/cli/index.js exists."
            )
        if self.ant_code_runtime == "wsl":
            return self._wsl_dashboard_command()
        command = [
            self.node_executable,
            self.ant_code_dashboard_entry,
        ]
        if self._dashboard_entry_uses_index(self.ant_code_dashboard_entry):
            command.append("dashboard")
        command.extend([
            "--project",
            self.workspace_dir,
            "--port",
            str(self.port),
            "--no-open",
        ])
        return command

    def _dashboard_entry_uses_index(self, entry_path):
        name = str(entry_path or "").replace("\\", "/").rstrip("/").split("/")[-1]
        return name == "index.js"

    def _wsl_dashboard_command(self):
        workspace_dir = self._wsl_workspace_dir()
        ant_code_root = self._wsl_ant_code_root_path()
        config_path = self._wsl_config_path()
        dashboard_entry = self._wsl_dashboard_entry_path()
        command = [self.wsl_executable]
        if self.wsl_distribution:
            command.extend(["-d", self.wsl_distribution])
        inner = [
            "env",
            f"LAB_AGENT_PACKAGE_ROOT={ant_code_root}",
            f"LAB_AGENT_CONFIG={config_path}",
            self.node_executable or "node",
            dashboard_entry,
        ]
        if self._dashboard_entry_uses_index(dashboard_entry):
            inner.append("dashboard")
        inner.extend([
            "--project",
            workspace_dir,
            "--port",
            str(self.port),
            "--no-open",
        ])
        command.extend([
            "--exec",
            "/bin/bash",
            "-lc",
            self._wsl_dashboard_shell_source(),
            "taxamask-antcode",
            workspace_dir,
        ])
        command.extend(inner)
        return command

    def _wsl_dashboard_shell_source(self):
        return r"""
set -e
workspace="$1"
shift
if [ -s "$HOME/.nvm/nvm.sh" ]; then
  . "$HOME/.nvm/nvm.sh"
fi
for dir in \
  "$HOME/.local/bin" \
  "$HOME/miniconda3/envs/taxamask/bin" \
  "$HOME/anaconda3/envs/taxamask/bin" \
  "$HOME/miniforge3/envs/taxamask/bin" \
  "$HOME/mambaforge/envs/taxamask/bin" \
  "$HOME/.conda/envs/taxamask/bin"; do
  if [ -d "$dir" ]; then
    PATH="$dir:$PATH"
  fi
done
export PATH
if ! command -v node >/dev/null 2>&1; then
  node_command="${4:-node}"
  if [ -n "$node_command" ] && [ "$node_command" != "${node_command#*/}" ] && [ -x "$node_command" ]; then
    :
  else
    echo "Cannot find Linux Node.js in WSL. Install Node.js 20+ in Ubuntu, or set TAXAMASK_WSL_NODE_EXE." >&2
    exit 127
  fi
fi
node_check="${4:-node}"
if [ "$node_check" = "${node_check#*/}" ]; then
  node_check="$(command -v "$node_check" 2>/dev/null || true)"
fi
if [ -z "$node_check" ] || ! "$node_check" -e "const major=Number(process.versions.node.split('.')[0]); process.exit(major>=20?0:1)" >/dev/null 2>&1; then
  echo "Node.js 20 or newer is required in WSL." >&2
  exit 127
fi
if [ ! -d "$workspace/vendor/ant-code/node_modules" ]; then
  echo "Ant-Code dependencies are missing in WSL. Run: cd \"$workspace/vendor/ant-code\" && npm ci" >&2
  exit 126
fi
cd "$workspace"
exec "$@"
""".strip()

    def _wsl_workspace_dir(self):
        return self._wsl_path(self.workspace_dir, "TAXAMASK_WSL_PROJECT_DIR")

    def _wsl_ant_code_root_path(self):
        override = os.environ.get("TAXAMASK_WSL_ANT_CODE_ROOT", "").strip()
        if override:
            return override
        project_override = os.environ.get("TAXAMASK_WSL_PROJECT_DIR", "").strip()
        if project_override:
            return project_override.rstrip("/") + "/vendor/ant-code"
        return self._wsl_path(self.ant_code_root)

    def _wsl_config_path(self):
        override = os.environ.get("TAXAMASK_WSL_ANT_CODE_CONFIG", "").strip()
        if override:
            return override
        project_override = os.environ.get("TAXAMASK_WSL_PROJECT_DIR", "").strip()
        if project_override:
            return project_override.rstrip("/") + "/AntSleap/config/taxamask_ant_code.config.json"
        return self._wsl_path(self.ant_code_config_path)

    def _wsl_dashboard_entry_path(self):
        override = os.environ.get("TAXAMASK_WSL_DASHBOARD_ENTRY", "").strip()
        if override:
            return override
        ant_root = self._wsl_ant_code_root_path()
        if ant_root:
            return ant_root.rstrip("/") + "/src/cli/dashboard.js"
        return self._wsl_path(self.ant_code_dashboard_entry)

    def _wsl_path(self, value, env_override=None):
        if env_override:
            override = os.environ.get(env_override, "").strip()
            if override:
                return override
        text = str(value or "").strip()
        if not text:
            return ""
        if text.startswith("/"):
            return text
        if sys.platform != "win32":
            return text
        converted = self._wslpath(text)
        return converted or self._fallback_windows_to_wsl_path(text)

    def _wslpath(self, value):
        if not self.wsl_executable:
            return ""
        command = [self.wsl_executable]
        if self.wsl_distribution:
            command.extend(["-d", self.wsl_distribution])
        command.extend(["--exec", "wslpath", "-a", str(value)])
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
                creationflags=self._creation_flags(),
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return str(result.stdout or "").strip()

    def _fallback_windows_to_wsl_path(self, value):
        text = str(value or "").replace("\\", "/")
        lowered = text.lower()
        for prefix in ("//wsl.localhost/", "//wsl$/"):
            if lowered.startswith(prefix):
                remainder = text[len(prefix):]
                parts = remainder.split("/", 1)
                return "/" + parts[1] if len(parts) > 1 else "/"
        if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
            drive = text[0].lower()
            rest = text[2:].lstrip("/")
            return f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
        return text

    def _dashboard_environment(self):
        env = os.environ.copy()
        if self.ant_code_runtime == "wsl":
            env["TAXAMASK_ANTCODE_RUNTIME_EFFECTIVE"] = "wsl"
            return env
        ant_root = Path(self.ant_code_root)
        if ant_root.exists():
            env["LAB_AGENT_PACKAGE_ROOT"] = str(ant_root)
        config_path = Path(self.ant_code_config_path)
        if config_path.exists():
            env["LAB_AGENT_CONFIG"] = str(config_path)
        return env

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        self.stack = QStackedWidget()
        self.stack.setObjectName("taxamaskAgentStack")
        self.fallback = QWidget()
        self.fallback.setObjectName("taxamaskAgentFallback")
        self.fallback.setMinimumHeight(360)
        fallback_layout = QVBoxLayout(self.fallback)
        fallback_layout.setContentsMargins(28, 28, 28, 28)
        fallback_layout.setSpacing(14)
        fallback_layout.addStretch(1)
        self.fallback_mark = QLabel()
        self.fallback_mark.setObjectName("taxamaskAgentFallbackMark")
        self.fallback_mark.setAlignment(Qt.AlignCenter)
        self._load_fallback_mark()
        fallback_layout.addWidget(self.fallback_mark)
        self.fallback_logo = QLabel("TaxaMask")
        self.fallback_logo.setObjectName("taxamaskAgentFallbackLogo")
        self.fallback_logo.setAlignment(Qt.AlignCenter)
        fallback_layout.addWidget(self.fallback_logo)
        self.fallback_detail = QLabel("")
        self.fallback_detail.setObjectName("taxamaskAgentFallbackDetail")
        self.fallback_detail.setAlignment(Qt.AlignCenter)
        self.fallback_detail.setWordWrap(True)
        fallback_layout.addWidget(self.fallback_detail)
        fallback_layout.addStretch(1)
        self.stack.addWidget(self.fallback)
        self.web_view = None
        root.addWidget(self.stack, 1)

        self.health_timer = QTimer(self)
        self.health_timer.setInterval(500)
        self.health_timer.timeout.connect(self._poll_dashboard_ready)
        self.prompt_retry_timer = QTimer(self)
        self.prompt_retry_timer.setSingleShot(True)
        self.prompt_retry_timer.timeout.connect(self._flush_pending_context_prompt)

    def _ensure_web_view(self):
        if self.browser_mode:
            return False
        if self.web_view is not None:
            return True
        if not _load_qtwebengine_classes():
            return False
        self.web_view = QWebEngineView()
        self.web_view.setObjectName("taxamaskAntCodeWebView")
        web_page_class = _ensure_agent_web_page_class()
        if web_page_class is not None:
            self.web_view.setPage(web_page_class(self, parent=self.web_view))
        self._configure_web_profile()
        self._install_web_bootstrap_script()
        self.web_view.loadFinished.connect(self._on_web_load_finished)
        self.stack.addWidget(self.web_view)
        return True

    def _load_fallback_mark(self):
        mark_path = Path(__file__).resolve().parents[1] / "assets" / "brand" / "taxamask_mark.png"
        if not mark_path.exists():
            self.fallback_mark.setVisible(False)
            return
        pixmap = QPixmap(str(mark_path))
        if pixmap.isNull():
            self.fallback_mark.setVisible(False)
            return
        self.fallback_mark.setPixmap(pixmap.scaled(280, 280, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.fallback_mark.setMinimumHeight(280)

    def _configure_web_profile(self):
        if self.web_view is None or QWebEngineProfile is None:
            return
        try:
            profile = QWebEngineProfile(self.web_view)
            self._web_profile = profile
            self._web_profile_storage_dir = tempfile.mkdtemp(prefix="taxamask_antcode_web_")
            if hasattr(profile, "setPersistentStoragePath"):
                profile.setPersistentStoragePath(self._web_profile_storage_dir)
            if hasattr(profile, "setCachePath"):
                profile.setCachePath(self._web_profile_storage_dir)
            if TaxaMaskAgentWebPage is not None:
                self.web_view.setPage(TaxaMaskAgentWebPage(self, profile=profile, parent=self.web_view))
            cache_type_enum = getattr(QWebEngineProfile, "HttpCacheType", QWebEngineProfile)
            no_cache = getattr(cache_type_enum, "NoCache")
            profile.setHttpCacheType(no_cache)
            profile.clearHttpCache()
        except Exception:
            return

    def _install_web_bootstrap_script(self):
        if self.web_view is None or QWebEngineScript is None:
            return
        try:
            script = QWebEngineScript()
            script.setName("taxamask-agent-embed-bootstrap")
            script.setSourceCode(self._web_bootstrap_source())
            injection_enum = getattr(QWebEngineScript, "InjectionPoint", QWebEngineScript)
            script.setInjectionPoint(getattr(injection_enum, "DocumentCreation"))
            world_enum = getattr(QWebEngineScript, "ScriptWorldId", QWebEngineScript)
            if hasattr(world_enum, "MainWorld"):
                script.setWorldId(getattr(world_enum, "MainWorld"))
            script.setRunsOnSubFrames(False)
            self.web_view.page().scripts().insert(script)
        except Exception:
            return

    def _web_embed_style_source(self):
        c = get_theme_config(self.current_theme)
        if c["is_light"]:
            page_background = c["bg_main"]
            workspace_background = c["bg_surface"]
            header_background = c["bg_surface_alt"]
            transcript_background = c["bg_surface"]
            composer_background = c["bg_surface_alt"]
            panel_background = c["bg_surface"]
            input_background = c["bg_input"]
            workspace_border = c["border"]
            soft_border = c["border"]
            text_color = c["text_main"]
            muted_color = c["text_dim"]
            accent_color = c["accent"]
            send_background = c["accent"]
            send_text = "#FFFFFF"
            code_background = "#F2F6FB"
            code_text = c["text_main"]
            progress_track = "#D8E4EF"
            summary_background = "#F8FBFE"
            summary_item_background = "#FFFFFF"
            scrollbar_track = "#EEF4FA"
            scrollbar_thumb = c["border_strong"]
            scrollbar_thumb_hover = "#9FB4C8"
            live_chip_background = "#F8FBFE"
            live_subagent_background = "#FFFFFF"
            live_chip_border = c["border"]
            live_cancel_background = "#FFF4F4"
            live_cancel_border = "#F8B4B4"
            option_background = "#F8FBFE"
            option_hover_background = "#EEF4FA"
            option_selected_background = c["selection"]
            warning_panel_background = "#FFF8E8"
            warning_panel_border = "#E9C978"
            danger_soft_background = "#FFF4F4"
            danger_soft_border = "#F8B4B4"
        else:
            page_background = (
                "radial-gradient(circle at 18% 0%, rgba(111, 143, 184, 0.10), transparent 34%), "
                "linear-gradient(105deg, transparent 0%, rgba(180, 193, 214, 0.055) 43%, transparent 58%), "
                "linear-gradient(135deg, #17263B 0%, #101B2D 42%, #070D1A 100%)"
            )
            workspace_background = (
                "linear-gradient(110deg, rgba(32, 51, 80, 0.94) 0%, "
                "rgba(20, 34, 56, 0.98) 39%, rgba(168, 181, 204, 0.075) 54%, "
                "rgba(13, 24, 41, 0.99) 68%, rgba(7, 13, 26, 1) 100%)"
            )
            header_background = (
                "linear-gradient(100deg, rgba(80, 110, 150, 0.16), "
                "rgba(164, 181, 205, 0.08), rgba(24, 42, 68, 0.84))"
            )
            transcript_background = (
                "linear-gradient(105deg, rgba(16, 27, 45, 0.98), rgba(9, 17, 31, 1) 48%, "
                "rgba(138, 157, 188, 0.045) 58%, rgba(7, 12, 22, 1))"
            )
            composer_background = "linear-gradient(180deg, rgba(13, 23, 39, 0.98), rgba(7, 12, 22, 1))"
            panel_background = "rgba(16, 28, 47, 0.94)"
            input_background = "rgba(17, 30, 50, 0.96)"
            workspace_border = "rgba(127, 154, 191, 0.44)"
            soft_border = "rgba(125, 149, 183, 0.42)"
            text_color = c["text_main"]
            muted_color = c["text_dim"]
            accent_color = c["accent"]
            send_background = "linear-gradient(135deg, #6F8FB8, #405F88)"
            send_text = "#F4F8FF"
            code_background = "rgba(8, 13, 23, 0.52)"
            code_text = c["text_main"]
            progress_track = "rgba(125, 149, 183, 0.28)"
            summary_background = "rgba(32, 32, 32, 0.5)"
            summary_item_background = "rgba(24, 24, 24, 0.42)"
            scrollbar_track = "rgba(7, 12, 22, 0.90)"
            scrollbar_thumb = "rgba(127, 154, 191, 0.55)"
            scrollbar_thumb_hover = "rgba(137, 167, 204, 0.72)"
            live_chip_background = "rgba(45, 45, 45, 0.86)"
            live_subagent_background = "rgba(45, 45, 45, 0.72)"
            live_chip_border = "rgba(255, 255, 255, 0.06)"
            live_cancel_background = "rgba(255, 133, 133, 0.08)"
            live_cancel_border = "rgba(255, 133, 133, 0.34)"
            option_background = "rgba(27, 27, 27, 0.70)"
            option_hover_background = "rgba(49, 50, 50, 0.92)"
            option_selected_background = "rgba(49, 50, 50, 0.92)"
            warning_panel_background = "#29251d"
            warning_panel_border = "#5b4b2a"
            danger_soft_background = "rgba(255, 133, 133, 0.08)"
            danger_soft_border = "rgba(255, 133, 133, 0.34)"
        return f"""
      :root {{
        --bg: {c['bg_main']} !important;
        --chrome: {c['bg_panel']} !important;
        --panel: {c['bg_surface']} !important;
        --panel-2: {c['bg_surface_alt']} !important;
        --panel-3: {c['bg_hover']} !important;
        --line: {soft_border} !important;
        --line-soft: {c['border']} !important;
        --text: {text_color} !important;
        --text-soft: {c['text_soft']} !important;
        --text-muted: {muted_color} !important;
        --accent: {accent_color} !important;
        --accent-2: {c['accent_hover']} !important;
        --warning: {c['warning']} !important;
        --danger: {c['error']} !important;
        --running: {c['success']} !important;
        --success: {c['success']} !important;
      }}
      .taxamask-embed,
      .taxamask-embed-body,
      html,
      body {{
        background: {page_background} !important;
        color: {text_color} !important;
        overflow: hidden !important;
      }}
      html.taxamask-embed,
      .taxamask-embed-body,
      .taxamask-embed * {{
        scrollbar-color: {scrollbar_thumb} {scrollbar_track} !important;
        scrollbar-width: thin !important;
      }}
      html.taxamask-embed::-webkit-scrollbar,
      .taxamask-embed-body::-webkit-scrollbar,
      .taxamask-embed *::-webkit-scrollbar {{
        height: 10px !important;
        width: 10px !important;
      }}
      html.taxamask-embed::-webkit-scrollbar-track,
      .taxamask-embed-body::-webkit-scrollbar-track,
      .taxamask-embed *::-webkit-scrollbar-track {{
        background: {scrollbar_track} !important;
      }}
      html.taxamask-embed::-webkit-scrollbar-thumb,
      .taxamask-embed-body::-webkit-scrollbar-thumb,
      .taxamask-embed *::-webkit-scrollbar-thumb {{
        background: {scrollbar_thumb} !important;
        border: 2px solid {scrollbar_track} !important;
        border-radius: 999px !important;
      }}
      html.taxamask-embed::-webkit-scrollbar-thumb:hover,
      .taxamask-embed-body::-webkit-scrollbar-thumb:hover,
      .taxamask-embed *::-webkit-scrollbar-thumb:hover {{
        background: {scrollbar_thumb_hover} !important;
      }}
      .taxamask-embed .app-shell,
      .app-shell {{
        background: {page_background} !important;
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        padding: 0 !important;
      }}
      .taxamask-embed .sidebar,
      .taxamask-embed .preview,
      .sidebar,
      .preview {{
        display: none !important;
      }}
      .taxamask-embed .workspace,
      .workspace {{
        background: {workspace_background} !important;
        border: 1px solid {workspace_border} !important;
        border-radius: 0 !important;
        grid-column: 1 / -1 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        min-width: 0 !important;
        width: 100% !important;
      }}
      .taxamask-embed .workspace-header,
      .workspace-header {{
        background: {header_background} !important;
        border-bottom: 1px solid {soft_border} !important;
        border-radius: 0 !important;
      }}
      .taxamask-embed .transcript,
      .transcript {{
        background: {transcript_background} !important;
      }}
      .taxamask-embed .composer-shell,
      .composer-shell {{
        background: {composer_background} !important;
        border-top: 1px solid {soft_border} !important;
      }}
      .taxamask-embed .empty-state,
      .taxamask-embed .message,
      .taxamask-embed .activity-card,
      .taxamask-embed .workflow-panel,
      .taxamask-embed .live-status,
      .taxamask-embed .shutdown-panel,
      .taxamask-embed .approval-panel,
      .taxamask-embed .question-panel,
      .taxamask-embed .trust-panel,
      .taxamask-embed .context-panel,
      .taxamask-embed .queue-panel,
      .empty-state,
      .message,
      .activity-card,
      .workflow-panel,
      .live-status,
      .shutdown-panel,
      .approval-panel,
      .question-panel,
      .trust-panel,
      .context-panel,
      .queue-panel {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .composer,
      .composer {{
        background: transparent !important;
      }}
      .taxamask-embed #prompt-input,
      #prompt-input {{
        background: {input_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .attach-button,
      .taxamask-embed .attachment-chip,
      .taxamask-embed .composer-footer span,
      .taxamask-embed .composer-footer button,
      .taxamask-embed .segmented,
      .taxamask-embed .segmented button.active {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed #send-button,
      #send-button {{
        background: {send_background} !important;
        border-color: {accent_color} !important;
        color: {send_text} !important;
      }}
      .taxamask-embed .workspace-local,
      .taxamask-embed .status-pill {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .workflow-strip,
      .taxamask-embed .workflow-strip-toggle,
      .taxamask-embed .workflow-strip-detail,
      .taxamask-embed .workflow-panel {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .workflow-strip-label,
      .taxamask-embed .workflow-kicker,
      .taxamask-embed .workflow-section-title,
      .taxamask-embed .workflow-strip-percent,
      .taxamask-embed .workflow-strip-chevron {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .workflow-strip-current,
      .taxamask-embed .workflow-title,
      .taxamask-embed .workflow-text {{
        color: {c['text_soft']} !important;
      }}
      .taxamask-embed .workflow-strip-toggle strong,
      .taxamask-embed .workflow-percent {{
        color: {accent_color} !important;
      }}
      .taxamask-embed .workflow-strip-meter,
      .taxamask-embed .workflow-meter {{
        background: {progress_track} !important;
      }}
      .taxamask-embed .workflow-strip-meter span,
      .taxamask-embed .workflow-meter span {{
        background: {accent_color} !important;
      }}
      .taxamask-embed .workflow-mark {{
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .workflow-item.in_progress .workflow-mark {{
        background: {c['success']} !important;
        border-color: {c['success']} !important;
      }}
      .taxamask-embed .workflow-item.completed .workflow-mark {{
        background: {c['success']} !important;
        border-color: {c['success']} !important;
      }}
      .taxamask-embed .live-status.has-background-subagents,
      .taxamask-embed .live-chip,
      .taxamask-embed .background-subagent-chip {{
        background: {live_chip_background} !important;
        border-color: {live_chip_border} !important;
        color: {muted_color} !important;
      }}
      .taxamask-embed .live-status.has-background-subagents .live-main,
      .taxamask-embed .live-subagent-head,
      .taxamask-embed .live-subagent-title {{
        color: {text_color} !important;
      }}
      .taxamask-embed .live-status.has-background-subagents .live-main::after,
      .taxamask-embed .live-subagent-meta,
      .taxamask-embed .live-subagent-summary {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .live-subagent-row {{
        background: {live_subagent_background} !important;
        border-color: {live_chip_border} !important;
        color: {muted_color} !important;
      }}
      .taxamask-embed .chip-pulse,
      .taxamask-embed .live-pulse {{
        background: {c['success']} !important;
      }}
      .taxamask-embed .background-subagent-chip.waiting .chip-pulse,
      .taxamask-embed .background-subagent-chip.stale .chip-pulse,
      .taxamask-embed .live-subagent-row.waiting .chip-pulse,
      .taxamask-embed .live-subagent-row.stale .chip-pulse {{
        background: {c['warning']} !important;
      }}
      .taxamask-embed .background-subagent-chip.lost .chip-pulse,
      .taxamask-embed .live-subagent-row.lost .chip-pulse {{
        background: {c['error']} !important;
      }}
      .taxamask-embed .live-subagent-cancel {{
        background: {live_cancel_background} !important;
        border-color: {live_cancel_border} !important;
        color: {c['error']} !important;
      }}
      .taxamask-embed .question-panel {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-read-pane,
      .taxamask-embed .question-prompt,
      .taxamask-embed .question-actions {{
        background: transparent !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-title,
      .taxamask-embed .approval-title,
      .taxamask-embed .trust-title,
      .taxamask-embed .context-title,
      .taxamask-embed .queue-title {{
        color: {accent_color} !important;
      }}
      .taxamask-embed .question-copy,
      .taxamask-embed .question-prompt-summary,
      .taxamask-embed .trust-copy,
      .taxamask-embed .context-copy,
      .taxamask-embed .queue-copy,
      .taxamask-embed .queue-more,
      .taxamask-embed .guide-feedback small,
      .taxamask-embed .guide-preview {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .question-choice,
      .taxamask-embed .queue-item,
      .taxamask-embed .queue-item span,
      .taxamask-embed .guide-feedback {{
        background: {option_background} !important;
        border-color: {soft_border} !important;
        color: {c['text_soft']} !important;
      }}
      .taxamask-embed .question-choice:hover {{
        background: {option_hover_background} !important;
        border-color: {workspace_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-choice.selected {{
        background: {option_selected_background} !important;
        border-color: {accent_color} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-choice small,
      .taxamask-embed .queue-item,
      .taxamask-embed .queue-item span {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .question-input {{
        background: {input_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-action-buttons button,
      .taxamask-embed .approval-actions button,
      .taxamask-embed .trust-actions button,
      .taxamask-embed .context-confirm-actions button,
      .taxamask-embed .context-actions button,
      .taxamask-embed .queue-head button {{
        background: {summary_item_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .question-action-buttons button[data-action="submit"],
      .taxamask-embed .approval-actions button:not(.danger),
      .taxamask-embed .trust-actions button,
      .taxamask-embed .queue-head button {{
        background: {accent_color} !important;
        border-color: {accent_color} !important;
        color: {send_text} !important;
      }}
      .taxamask-embed .approval-panel {{
        background: {warning_panel_background} !important;
        border-color: {warning_panel_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .approval-preview {{
        background: {code_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .approval-actions button.danger,
      .taxamask-embed .context-confirm-actions button.danger,
      .taxamask-embed .context-actions #context-clear,
      .taxamask-embed .live-subagent-cancel {{
        background: {danger_soft_background} !important;
        border-color: {danger_soft_border} !important;
        color: {c['error']} !important;
      }}
      .taxamask-embed .shutdown-panel,
      .taxamask-embed .trust-panel,
      .taxamask-embed .context-panel,
      .taxamask-embed .queue-panel,
      .taxamask-embed .model-panel,
      .taxamask-embed .model-config-card {{
        background: {panel_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .shutdown-title,
      .taxamask-embed .model-panel-title,
      .taxamask-embed .model-config-head h2,
      .taxamask-embed .model-option-name,
      .taxamask-embed .gateway-profile-main {{
        color: {text_color} !important;
      }}
      .taxamask-embed .shutdown-copy,
      .taxamask-embed .model-panel-subtitle,
      .taxamask-embed .model-config-kicker,
      .taxamask-embed .model-config-grid span,
      .taxamask-embed .model-config-toggles label,
      .taxamask-embed .model-config-note,
      .taxamask-embed .model-panel-empty,
      .taxamask-embed .model-option-id,
      .taxamask-embed .model-option-agent,
      .taxamask-embed .gateway-profile-meta,
      .taxamask-embed .model-delete-confirm-copy {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .model-agent-sync,
      .taxamask-embed .gateway-profile-option,
      .taxamask-embed .model-option-row,
      .taxamask-embed .model-option-tags span {{
        background: {option_background} !important;
        border-color: {soft_border} !important;
        color: {c['text_soft']} !important;
      }}
      .taxamask-embed .gateway-profile-option:hover,
      .taxamask-embed .gateway-profile-option.active,
      .taxamask-embed .model-option-row:hover,
      .taxamask-embed .model-option-row.active {{
        background: {option_hover_background} !important;
        border-color: {workspace_border} !important;
      }}
      .taxamask-embed .model-option-row.confirming-delete {{
        border-color: {danger_soft_border} !important;
      }}
      .taxamask-embed .model-option,
      .taxamask-embed .model-status-caret {{
        background: transparent !important;
        border-color: transparent !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .model-manage-button,
      .taxamask-embed .model-edit-button,
      .taxamask-embed .model-delete-button,
      .taxamask-embed .model-config-actions button,
      .taxamask-embed .shutdown-actions button {{
        background: {summary_item_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .model-delete-button:hover,
      .taxamask-embed .model-delete-button.confirm,
      .taxamask-embed .shutdown-actions #shutdown-confirm {{
        background: {danger_soft_background} !important;
        border-color: {danger_soft_border} !important;
        color: {c['error']} !important;
      }}
      .taxamask-embed .model-config-actions button[type="submit"] {{
        background: {accent_color} !important;
        border-color: {accent_color} !important;
        color: {send_text} !important;
      }}
      .taxamask-embed .model-config-grid input,
      .taxamask-embed .model-config-grid select,
      .taxamask-embed .model-config-grid select option {{
        background: {input_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .model-config-backdrop {{
        background: rgba(16, 32, 51, 0.18) !important;
      }}
      .taxamask-embed .md-code-frame,
      .taxamask-embed .md-draft-plain,
      .taxamask-embed .md-math-block,
      .taxamask-embed .md-mermaid-frame,
      .taxamask-embed .md-data-frame,
      .taxamask-embed .md-toc,
      .taxamask-embed .md-table-wrap,
      .taxamask-embed .data-table-wrap {{
        background: {code_background} !important;
        border-color: {soft_border} !important;
        color: {code_text} !important;
      }}
      .taxamask-embed .md-code-bar,
      .taxamask-embed .md-draft-plain-label,
      .taxamask-embed .md-rich-label,
      .taxamask-embed .md-rich-bar {{
        background: {summary_background} !important;
        border-color: {soft_border} !important;
        color: {muted_color} !important;
      }}
      .taxamask-embed .md-copy-code,
      .taxamask-embed .data-copy {{
        background: {summary_item_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .md-copy-code:hover,
      .taxamask-embed .data-copy:hover {{
        background: {option_hover_background} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .md-code,
      .taxamask-embed .md-code code,
      .taxamask-embed .md-raw-source,
      .taxamask-embed .md-raw-source code {{
        background: transparent !important;
        border-color: transparent !important;
        color: {code_text} !important;
      }}
      .taxamask-embed .markdown-body th,
      .taxamask-embed .data-table th {{
        background: {summary_background} !important;
        border-color: {soft_border} !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .markdown-body td,
      .taxamask-embed .data-table td {{
        border-color: {soft_border} !important;
        color: {c['text_soft']} !important;
      }}
      .taxamask-embed .draft-summary,
      .taxamask-embed .activity-summary {{
        background: {summary_background} !important;
        border-color: {soft_border} !important;
        color: {muted_color} !important;
      }}
      .taxamask-embed .draft-summary summary,
      .taxamask-embed .activity-summary summary {{
        background: transparent !important;
        color: {text_color} !important;
      }}
      .taxamask-embed .draft-summary summary span:nth-child(2),
      .taxamask-embed .draft-summary-title,
      .taxamask-embed .summary-row {{
        color: {text_color} !important;
      }}
      .taxamask-embed .draft-summary-meta,
      .taxamask-embed .draft-summary-note {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .draft-summary-list,
      .taxamask-embed .activity-summary-list {{
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .draft-summary-item {{
        background: {summary_item_background} !important;
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .activity-card pre,
      .taxamask-embed .activity-card code,
      .taxamask-embed .message pre,
      .taxamask-embed .message code,
      .taxamask-embed .tool-preview,
      .taxamask-embed .tool-output,
      .taxamask-embed .tool-result,
      .taxamask-embed .code-preview,
      .taxamask-embed .approval-preview,
      .taxamask-embed pre,
      .taxamask-embed code {{
        background: {code_background} !important;
        color: {code_text} !important;
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .activity-detail,
      .taxamask-embed .activity-meta,
      .taxamask-embed .muted,
      .taxamask-embed .hint,
      .taxamask-embed .composer-footer {{
        color: {muted_color} !important;
      }}
      .taxamask-embed .progress-track,
      .taxamask-embed .task-progress,
      .taxamask-embed .progress-bar-track {{
        background: {progress_track} !important;
        border-color: {soft_border} !important;
      }}
      .taxamask-embed .progress-bar,
      .taxamask-embed .progress-fill,
      .taxamask-embed .task-progress-fill {{
        background: {accent_color} !important;
      }}
    """.rstrip()

    def _web_bootstrap_source(self):
        return r"""
(() => {
  if (window.__taxamaskAgentBootstrapInstalled) return;
  window.__taxamaskAgentBootstrapInstalled = true;
  const taxamaskEmbedCss = __TAXAMASK_EMBED_STYLE__;
  const reloadKey = "__taxamaskAgentJsonReloaded";
  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
  const guardedApiPath = (input) => {
    try {
      const raw = typeof input === "string" ? input : input && input.url;
      if (!raw) return "";
      const url = new URL(raw, window.location.href);
      if (url.origin !== window.location.origin) return "";
      const bootJsonPaths = new Set(["/api/status", "/api/trust", "/api/sessions"]);
      return bootJsonPaths.has(url.pathname) ? url.pathname : "";
    } catch (_error) {
      return "";
    }
  };
  const installStyle = () => {
    if (!document.head) return;
    document.documentElement.classList.add("taxamask-embed");
    document.body?.classList.add("taxamask-embed-body");
    let style = document.querySelector("#taxamask-agent-embed-style");
    if (!style) {
      style = document.createElement("style");
      style.id = "taxamask-agent-embed-style";
      document.head.appendChild(style);
    }
    style.textContent = taxamaskEmbedCss;
  };
  installStyle();
  document.addEventListener("DOMContentLoaded", installStyle, { once: true });

  const nativeFetch = window.fetch ? window.fetch.bind(window) : null;
  if (nativeFetch) {
    window.fetch = async (input, init) => {
      const path = guardedApiPath(input);
      if (!path) return nativeFetch(input, init);
      let lastResponse = null;
      let lastError = null;
      for (let attempt = 0; attempt < 4; attempt += 1) {
        try {
          const response = await nativeFetch(input, init);
          lastResponse = response;
          const text = await response.clone().text();
          const trimmed = text.trim();
          if (trimmed.length > 0) {
            JSON.parse(trimmed);
            return response;
          }
          lastError = new Error(`${path} returned an empty JSON response`);
        } catch (error) {
          lastError = error;
        }
        if (attempt < 3) await sleep(160 * (attempt + 1));
      }
      const detail = lastError && lastError.message ? lastError.message : `${path} failed before returning JSON`;
      return new Response(JSON.stringify({ ok: false, error: detail }), {
        status: lastResponse ? lastResponse.status || 502 : 502,
        headers: { "content-type": "application/json; charset=utf-8" }
      });
    };
  }

  window.addEventListener("unhandledrejection", (event) => {
    const message = event.reason && (event.reason.message || String(event.reason));
    if (!/Unexpected end of JSON input|empty JSON response|Expected double-quoted property name/i.test(message || "")) return;
    try {
      if (window.sessionStorage.getItem(reloadKey)) return;
      window.sessionStorage.setItem(reloadKey, "1");
      event.preventDefault();
      window.setTimeout(() => window.location.reload(), 350);
    } catch (_error) {
      return;
    }
  });
})();
""".replace("__TAXAMASK_EMBED_STYLE__", json.dumps(self._web_embed_style_source()))

    def _sync_web_embed_theme(self):
        if self.web_view is None:
            return
        css = json.dumps(self._web_embed_style_source())
        self.web_view.page().runJavaScript(
            f"""
            (() => {{
              const css = {css};
              if (!document.head) return false;
              document.documentElement.classList.add("taxamask-embed");
              document.body?.classList.add("taxamask-embed-body");
              let style = document.querySelector("#taxamask-agent-embed-style");
              if (!style) {{
                style = document.createElement("style");
                style.id = "taxamask-agent-embed-style";
                document.head.appendChild(style);
              }}
              style.textContent = css;
              return true;
            }})();
            """
        )

    def _apply_style(self, theme=None):
        self.current_theme = normalize_theme(theme or getattr(self, "current_theme", "dark"))
        c = get_theme_config(self.current_theme)
        self.setStyleSheet(
            f"""
            QWidget#taxamaskAgentPanel {{
                background: {c['bg_surface_gradient']};
                border: 1px solid {c['glow_border'] if not c['is_light'] else c['border']};
                border-radius: 16px;
            }}
            QWidget#taxamaskAgentFallback {{
                background: {c['bg_surface_alt_gradient']};
                border: 1px solid {c['border_strong']};
                border-radius: 12px;
            }}
            QLabel#taxamaskAgentFallbackLogo {{
                color: {c['text_main']};
                font-family: "Copperplate Gothic Bold", "Cambria", "Georgia", "Times New Roman", "Microsoft YaHei UI";
                font-size: 52px;
                font-weight: 800;
                letter-spacing: 0px;
                padding: 0 0 4px 0;
            }}
            QLabel#taxamaskAgentFallbackMark {{
                padding: 0;
                margin: 0;
            }}
            QLabel#taxamaskAgentFallbackDetail {{
                color: {c['text_dim']};
                font-size: 12px;
                padding: 2px 20px;
            }}
            QStackedWidget#taxamaskAgentStack {{
                background: transparent;
                border: none;
            }}
            """
        )

    def set_theme(self, theme):
        self._apply_style(theme)
        self._sync_web_embed_theme()

    def set_language(self, lang):
        self.lang = lang
        if self.is_running():
            status = at("Ant-Code Dashboard is ready.", lang)
        else:
            status = at("Ant-Code Dashboard is not running.", lang)
        self._update_status_label(status)
        self._update_fallback()

    def update_runtime_status(self, model_status=None, workflow=None, project=None, state=None):
        if project:
            self._project_display = project

    def set_context(self, context=None, announce=False):
        self._context = dict(context or {})
        if not announce:
            return
        prompt = self._context_prompt(self._context)
        if prompt:
            self._send_context_prompt(prompt)

    def set_prompt_text(self, prompt):
        self._send_context_prompt(str(prompt or ""))

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def start_dashboard(self):
        if self.is_running():
            self._prepare_dashboard_load(reset=True)
            return
        if not self.browser_mode and not self._ensure_web_view():
            self.browser_mode = True
            self._update_fallback()
        try:
            self.port = find_free_port(7410)
            self.dashboard_url = f"http://127.0.0.1:{self.port}"
            self._load_retries = 0
            self._pending_prompt_attempts = 0
            self._preflight_checks_remaining = 0
            self._preflight_error = ""
            self._embedded_page_error = ""
            self._json_health_warning = self._dashboard_workspace_json_warning()
            self._json_health_error = self._dashboard_json_health_error()
            if self._json_health_error:
                raise RuntimeError(self._json_health_error)
            env = self._dashboard_environment()
            command = self._dashboard_command()
            self._open_dashboard_log()
            self.process = subprocess.Popen(
                command,
                cwd=self.workspace_dir,
                env=env,
                stdout=self._dashboard_log_handle or subprocess.DEVNULL,
                stderr=self._dashboard_log_handle or subprocess.DEVNULL,
                creationflags=self._creation_flags(),
            )
        except Exception as exc:
            self._close_dashboard_log()
            self.process = None
            self.dashboard_url = ""
            self._preflight_error = str(exc)
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._preflight_error))
            self._update_fallback()
            return
        self._health_checks_remaining = 80
        self._update_status_label(at("Starting Ant-Code Dashboard...", self.lang))
        self._update_fallback()
        self.health_timer.start()

    def _open_dashboard_log(self):
        self._close_dashboard_log(remove=True)
        try:
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                errors="replace",
                prefix="taxamask_antcode_",
                suffix=".log",
                delete=False,
            )
        except Exception:
            self._dashboard_log_path = ""
            self._dashboard_log_handle = None
            return
        self._dashboard_log_path = handle.name
        self._dashboard_log_handle = handle

    def _close_dashboard_log(self, remove=False):
        handle = self._dashboard_log_handle
        self._dashboard_log_handle = None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if remove and self._dashboard_log_path:
            try:
                Path(self._dashboard_log_path).unlink(missing_ok=True)
            except Exception:
                pass
            self._dashboard_log_path = ""

    def _dashboard_log_tail(self, max_chars=1200):
        handle = self._dashboard_log_handle
        if handle is not None:
            try:
                handle.flush()
            except Exception:
                pass
        path = self._dashboard_log_path
        if not path:
            return ""
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        text = text.strip()
        if not text:
            return ""
        return text[-int(max_chars):]

    def _dashboard_exit_error(self):
        detail = self._dashboard_log_tail()
        if not detail:
            return at("Ant-Code process exited.", self.lang)
        return f"{at('Ant-Code process exited.', self.lang)} {detail}"

    def _creation_flags(self):
        if sys.platform != "win32":
            return 0
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _poll_dashboard_ready(self):
        if not self.is_running():
            self.health_timer.stop()
            self._preflight_error = self._dashboard_exit_error()
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._preflight_error))
            self._close_dashboard_log()
            self._update_fallback()
            return
        if self._health_checks_remaining <= 0:
            self.health_timer.stop()
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format("timeout"))
            self._update_fallback()
            return
        self._health_checks_remaining -= 1
        try:
            import urllib.request

            with urllib.request.urlopen(f"{self.dashboard_url}/api/status", timeout=0.5) as response:
                if response.status == 200:
                    self.health_timer.stop()
                    self._on_dashboard_ready()
        except Exception:
            return

    def _on_dashboard_ready(self):
        self._close_dashboard_log()
        self._update_status_label(at("Ant-Code Dashboard is ready.", self.lang))
        if self.browser_mode:
            self.open_dashboard_in_browser(start_if_needed=False)
        self._prepare_dashboard_load(reset=True)

    def _prepare_dashboard_load(self, reset=False):
        if reset:
            self._preflight_checks_remaining = 6
            self._load_retries = 0
            self._embedded_page_error = ""
        if not self.dashboard_url:
            return
        if not self.is_running():
            self._update_status_label(at("Ant-Code process exited.", self.lang))
            self._update_fallback()
            return
        if self.browser_mode:
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        if not self._ensure_web_view():
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        if self._preflight_dashboard(report_error=False):
            QTimer.singleShot(250, self._load_dashboard)
            return
        self._update_fallback()
        if self._preflight_checks_remaining > 0:
            self._preflight_checks_remaining -= 1
            self._update_status_label(at("Starting Ant-Code Dashboard...", self.lang))
            QTimer.singleShot(350, self._prepare_dashboard_load)
            return
        self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._preflight_error))

    def _load_dashboard(self):
        if not self.dashboard_url:
            return
        if not self.browser_mode:
            self._ensure_web_view()
        if self.web_view is None:
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        self.stack.setCurrentWidget(self.web_view)
        cache_key = f"taxamask_embed=1&taxamask_lang={self.lang}&reload={self._load_retries}"
        self.web_view.load(QUrl(f"{self.dashboard_url}/?{cache_key}"))

    def _web_post_load_source(self):
        if self.lang == "zh":
            texts = {
                "htmlLang": "zh-CN",
                "localLabel": "TaxaMask Agent · 源码只读保护已启用",
                "subtitle": "Ant-Code native",
                "emptyTitle": "我会在当前 TaxaMask 仓库中协助排查",
                "emptyCopy": "可以读源码和排查配置；外部模型适配和 TaxaMask 源码开发会分别请求确认。",
                "promptPlaceholder": "把遇到的问题、配置目标或标注流程疑问发给 TaxaMask Agent",
                "trustTitle": "信任此工作区？",
                "trustButton": "信任并继续",
                "trustProcess": "当前为高敏模式，本次确认只授权当前 Dashboard 进程。",
                "trustPersist": "确认后会记录这个工作区，下次从同一路径启动可继续使用。",
                "modeDescriptions": {
                    "plan": "写入和命令需确认",
                    "workspace": "工作区常规操作自动同意",
                    "fullAccess": "本机工具和网络自动同意",
                },
                "modeLabels": {
                    "plan": "计划确认",
                    "workspace": "工作区权限",
                    "fullAccess": "完全访问",
                },
                "textMap": {
                    "空闲": "空闲",
                    "发送": "发送",
                    "待信任": "待信任",
                    "运行中": "运行中",
                    "关闭": "关闭",
                    "清空上下文": "清空上下文",
                    "压缩上下文": "压缩上下文",
                },
                "translatePatterns": False,
            }
        else:
            texts = {
                "htmlLang": "en",
                "localLabel": "TaxaMask Agent · source-read guard enabled",
                "subtitle": "Ant-Code native",
                "emptyTitle": "I can help inspect this TaxaMask workspace",
                "emptyCopy": "I can read source files and check configuration. External model adaptation and source-code changes will ask for confirmation when needed.",
                "promptPlaceholder": "Ask TaxaMask Agent about an error, model setup, annotation workflow, or project state",
                "trustTitle": "Trust this workspace?",
                "trustButton": "Trust and continue",
                "trustProcess": "High-sensitivity mode is active. This confirmation only trusts the current Dashboard process.",
                "trustPersist": "After confirmation, this workspace path is remembered for future launches.",
                "modeDescriptions": {
                    "plan": "Confirm writes and commands",
                    "workspace": "Auto-approve regular workspace operations",
                    "fullAccess": "Auto-approve local tools and network access",
                },
                "modeLabels": {
                    "plan": "Plan confirm",
                    "workspace": "Workspace",
                    "fullAccess": "Full access",
                },
                "textMap": {
                    "空闲": "Idle",
                    "发送": "Send",
                    "待信任": "Trust required",
                    "运行中": "Running",
                    "关闭": "Close",
                    "清空上下文": "Clear context",
                    "压缩上下文": "Compact context",
                    "切换模型": "Switch model",
                    "编辑当前": "Edit current",
                    "添加模型": "Add model",
                    "切换时同步子智能体默认模型": "Also sync default sub-agent models when switching",
                    "没有已注册模型": "No registered models",
                    "当前": "Current",
                    "编辑": "Edit",
                    "删除": "Delete",
                    "确认删除": "Confirm delete",
                    "删除中": "Deleting",
                    "文本": "Text",
                    "上下文": "context",
                    "本地配置": "Local configuration",
                    "编辑模型网关": "Edit model gateway",
                    "添加模型网关": "Add model gateway",
                    "关闭模型配置": "Close model configuration",
                    "模型 ID": "Model ID",
                    "上下文窗口": "Context window",
                    "保存后切换到这个模型": "Switch to this model after saving",
                    "保存后同步子智能体": "Sync sub-agents after saving",
                    "配置会写入 .lab-agent/config.json；该目录默认不进 Git。Key 不会在这里回显。": "Configuration is written to .lab-agent/config.json. This directory is ignored by Git by default. Keys are not displayed here.",
                    "取消": "Cancel",
                    "保存中": "Saving",
                    "保存并使用": "Save and use",
                    "未配置网关": "Gateway not configured",
                    "Key 已配置": "Key configured",
                    "未配置 Key": "Key missing",
                    "无 Key": "No key",
                    "视觉": "Vision",
                    "子智能体": "Sub-agent",
                    "编辑这个模型配置": "Edit this model configuration",
                    "删除这个已注册模型": "Delete this registered model",
                    "再次点击确认删除": "Click again to confirm deletion",
                    "再次点击确认删除；这是当前网关最后一个模型，会清空当前网关配置。": "Click again to confirm deletion. This is the last model for the current gateway, so the current gateway configuration will be cleared.",
                    "再次点击确认删除；如删除当前模型，会自动切到同一网关的下一个模型。": "Click again to confirm deletion. If the current model is deleted, TaxaMask will switch to another model on the same gateway.",
                },
                "translatePatterns": True,
            }
        return """
            (() => {
              const taxamaskText = __TAXAMASK_TEXT__;
              const translateTextValue = (value) => {
                const original = String(value ?? '');
                const trimmed = original.trim();
                if (!trimmed) return original;
                if (taxamaskText.textMap && Object.prototype.hasOwnProperty.call(taxamaskText.textMap, trimmed)) {
                  return taxamaskText.textMap[trimmed];
                }
                if (!taxamaskText.translatePatterns) return original;
                let translated = trimmed
                  .replaceAll('Key 已配置', 'Key configured')
                  .replaceAll('未配置 Key', 'Key missing')
                  .replaceAll('未配置网关', 'Gateway not configured')
                  .replaceAll('无 Key', 'No key');
                let match = translated.match(/^模型\\s+(.+)$/);
                if (match) return `Model ${match[1]}`;
                match = translated.match(/^上下文\\s+(.+)$/);
                if (match) return `Context ${match[1]}`;
                match = translated.match(/^(\\d+)\\s+模型$/);
                if (match) return `${match[1]} models`;
                match = translated.match(/^([0-9.]+[kKmM]?)\\s+上下文$/);
                if (match) return `${match[1]} context`;
                match = translated.match(/^子智能体\\s+(.+)$/);
                if (match) return `Sub-agent ${match[1]}`;
                return translated;
              };
              const setTranslatedText = (node) => {
                if (!node) return;
                const translated = translateTextValue(node.textContent);
                if (translated !== node.textContent.trim()) node.textContent = translated;
              };
              const translateDirectTextNodes = (node) => {
                if (!node) return;
                node.childNodes.forEach((child) => {
                  if (child.nodeType !== Node.TEXT_NODE) return;
                  const raw = child.nodeValue || '';
                  const translated = translateTextValue(raw);
                  if (translated !== raw.trim()) child.nodeValue = raw.replace(raw.trim(), translated);
                });
              };
              const translateAttributes = (node) => {
                if (!node || !node.getAttribute) return;
                ['title', 'aria-label'].forEach((attr) => {
                  const raw = node.getAttribute(attr);
                  if (!raw) return;
                  const translated = translateTextValue(raw);
                  if (translated !== raw.trim()) node.setAttribute(attr, translated);
                });
              };
              const applyTaxaMaskDefaults = () => {
                document.documentElement.lang = taxamaskText.htmlLang || 'en';
                const workspaceButton = document.querySelector('#permission-mode button[data-mode="workspace"]');
                if (workspaceButton && !workspaceButton.classList.contains('active')) {
                  workspaceButton.click();
                }
                const localLabel = document.querySelector('.workspace-local span:last-child');
                if (localLabel) localLabel.textContent = taxamaskText.localLabel;
                const brand = document.querySelector('.brand-name');
                if (brand) brand.textContent = 'TaxaMask Agent';
                const subtitle = document.querySelector('.brand-subtitle');
                if (subtitle) subtitle.textContent = taxamaskText.subtitle;
                const emptyKicker = document.querySelector('.empty-kicker');
                if (emptyKicker) emptyKicker.textContent = 'TaxaMask Agent';
                const emptyTitle = document.querySelector('.empty-title');
                if (emptyTitle) emptyTitle.textContent = taxamaskText.emptyTitle;
                const emptyCopy = document.querySelector('.empty-copy');
                if (emptyCopy) emptyCopy.textContent = taxamaskText.emptyCopy;
                const prompt = document.querySelector('#prompt-input');
                if (prompt) prompt.placeholder = taxamaskText.promptPlaceholder;
                document.querySelectorAll('#permission-mode button[data-mode]').forEach((button) => {
                  const label = taxamaskText.modeLabels && taxamaskText.modeLabels[button.dataset.mode];
                  if (label) button.textContent = label;
                });
                const activeMode = document.querySelector('#permission-mode button.active')?.dataset?.mode || 'workspace';
                const modeDescription = document.querySelector('#mode-description');
                if (modeDescription && taxamaskText.modeDescriptions && taxamaskText.modeDescriptions[activeMode]) {
                  modeDescription.textContent = taxamaskText.modeDescriptions[activeMode];
                }
                const mapText = (node) => {
                  if (!node || !taxamaskText.textMap) return;
                  const current = node.textContent.trim();
                  if (Object.prototype.hasOwnProperty.call(taxamaskText.textMap, current)) {
                    node.textContent = taxamaskText.textMap[current];
                  }
                };
                ['#run-status', '#send-button', '#header-shutdown-button', '#context-clear', '#context-compact'].forEach((selector) => {
                  mapText(document.querySelector(selector));
                });
                const dynamicTextSelectors = [
                  '#model-status .model-status-main',
                  '#model-status .model-status-tag',
                  '#context-status',
                  '.model-panel-title',
                  '.model-panel-subtitle',
                  '.model-panel-empty',
                  '.model-manage-button',
                  '.model-agent-sync span',
                  '.gateway-profile-meta',
                  '.model-option-current',
                  '.model-option-agent',
                  '.model-option-tags span',
                  '.model-edit-button',
                  '.model-delete-button',
                  '.model-delete-confirm-copy',
                  '.model-config-kicker',
                  '#model-config-title',
                  '.model-config-grid label > span',
                  '.model-config-note',
                  '.model-config-actions button'
                ].join(',');
                document.querySelectorAll(dynamicTextSelectors).forEach(setTranslatedText);
                document.querySelectorAll('.model-config-toggles label').forEach(translateDirectTextNodes);
                document.querySelectorAll('[title], [aria-label]').forEach(translateAttributes);
                const trustTitle = document.querySelector('.trust-title');
                if (trustTitle) trustTitle.textContent = taxamaskText.trustTitle;
                const trustButton = document.querySelector('#trust-panel button[data-action="trust"]');
                if (trustButton && !trustButton.disabled) trustButton.textContent = taxamaskText.trustButton;
                const trustCopies = document.querySelectorAll('.trust-copy');
                if (trustCopies.length > 1) {
                  const raw = trustCopies[1].textContent || '';
                  trustCopies[1].textContent = raw.includes('高敏') || raw.toLowerCase().includes('high-sensitivity')
                    ? taxamaskText.trustProcess
                    : taxamaskText.trustPersist;
                }
              };
              const trustPending = () => {
                const send = document.querySelector('#send-button');
                const trustPanel = document.querySelector('#trust-panel');
                const sendText = send ? send.textContent.trim() : '';
                const panelVisible = trustPanel
                  && !trustPanel.classList.contains('hidden')
                  && trustPanel.textContent.trim().length > 0;
                return ['待信任', 'Trust required'].includes(sendText) || Boolean(panelVisible);
              };
              const postTrust = async () => {
                try {
                  const response = await fetch('/api/trust', {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: '{}'
                  });
                  const result = await response.json();
                  return Boolean(result && result.ok !== false && result.trust && result.trust.trusted);
                } catch (_error) {
                  return false;
                }
              };
              applyTaxaMaskDefaults();
              const defaultsTimer = window.setInterval(applyTaxaMaskDefaults, 300);
              window.setTimeout(() => window.clearInterval(defaultsTimer), 5000);

              const trustReloadKey = '__taxamaskAgentTrustReloaded';
              let trustAttempts = 0;
              let backendTrusted = false;
              const reconcileTrust = async () => {
                trustAttempts += 1;
                applyTaxaMaskDefaults();
                const trustButton = document.querySelector('#trust-panel button[data-action="trust"]');
                if (trustButton && !trustButton.disabled) {
                  trustButton.click();
                }
                backendTrusted = (await postTrust()) || backendTrusted;
                if (!trustPending()) {
                  window.clearInterval(trustTimer);
                  return;
                }
                if (backendTrusted && trustAttempts >= 10) {
                  try {
                    if (!window.sessionStorage.getItem(trustReloadKey)) {
                      window.sessionStorage.setItem(trustReloadKey, '1');
                      window.location.reload();
                    }
                  } catch (_error) {
                    return;
                  }
                }
                if (trustAttempts >= 20) {
                  window.clearInterval(trustTimer);
                }
              };
              const trustTimer = window.setInterval(() => { void reconcileTrust(); }, 250);
              document.querySelector('#permission-mode')?.addEventListener('click', () => window.setTimeout(applyTaxaMaskDefaults, 0));
              let taxamaskMutationPending = false;
              const scheduleTaxaMaskDefaults = () => {
                if (taxamaskMutationPending) return;
                taxamaskMutationPending = true;
                window.requestAnimationFrame(() => {
                  taxamaskMutationPending = false;
                  applyTaxaMaskDefaults();
                });
              };
              if (document.body && window.MutationObserver) {
                new MutationObserver(scheduleTaxaMaskDefaults).observe(document.body, {
                  childList: true,
                  subtree: true,
                  characterData: true,
                });
              }
              document.addEventListener('click', () => window.setTimeout(applyTaxaMaskDefaults, 0), true);
              void reconcileTrust();
            })();
            """.replace("__TAXAMASK_TEXT__", json.dumps(texts, ensure_ascii=False))

    def _on_web_load_finished(self, ok):
        if self.web_view is None:
            return
        if not ok:
            self._embedded_page_error = "embedded page load failed"
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._embedded_page_error))
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        self._sync_web_embed_theme()
        self.web_view.page().runJavaScript(self._web_post_load_source())
        self._ensure_trusted()
        QTimer.singleShot(1200, self._verify_embedded_page_ready)
        if self._pending_context_prompt:
            self._schedule_pending_context_prompt_flush(700)

    def _verify_embedded_page_ready(self):
        if self.web_view is None or not self.dashboard_url:
            return
        self.web_view.page().runJavaScript(
            """
            (() => {
              const project = document.querySelector('#project-path')?.textContent?.trim() || '';
              const send = document.querySelector('#send-button');
              const transcript = document.querySelector('#transcript');
              const trustPanel = document.querySelector('#trust-panel');
              const sendText = send ? send.textContent.trim() : '';
              const panelVisible = trustPanel
                && !trustPanel.classList.contains('hidden')
                && trustPanel.textContent.trim().length > 0;
              const loadingProject = ['加载中', 'Loading'].includes(project);
              const trustSendText = ['待信任', 'Trust required'].includes(sendText);
              return Boolean(send && transcript && project && !loadingProject && !trustSendText && !panelVisible);
            })();
            """,
            self._handle_embedded_page_ready,
        )

    def _handle_embedded_page_ready(self, ready):
        if ready:
            self._embedded_page_error = ""
            if self.web_view is not None:
                self.web_view.page().runJavaScript(
                    "try { sessionStorage.removeItem('__taxamaskAgentJsonReloaded'); sessionStorage.removeItem('__taxamaskAgentTrustReloaded'); } catch (error) {}"
                )
            self._flush_pending_context_prompt()
            return
        if not self.is_running() or self.web_view is None:
            return
        max_retries = 4 if self._pending_context_prompt else 2
        if self._load_retries >= max_retries:
            self._embedded_page_error = "embedded page init failed"
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._embedded_page_error))
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        self._load_retries += 1
        self._update_status_label(at("Starting Ant-Code Dashboard...", self.lang))
        if self._pending_context_prompt:
            self._schedule_pending_context_prompt_flush(900)
        QTimer.singleShot(350, self._load_dashboard)

    def _ensure_trusted(self):
        if not self.dashboard_url:
            return False
        try:
            import urllib.request

            request = urllib.request.Request(f"{self.dashboard_url}/api/trust", data=b"{}", method="POST")
            request.add_header("content-type", "application/json")
            with urllib.request.urlopen(request, timeout=2.0) as response:
                body = response.read().decode("utf-8", errors="replace")
                if response.status < 200 or response.status >= 300:
                    return False
            data = json.loads(body) if body.strip() else {}
            trust = data.get("trust") if isinstance(data, dict) else {}
            return bool(data.get("ok") is not False and isinstance(trust, dict) and trust.get("trusted") is True)
        except Exception:
            return False

    def _preflight_dashboard(self, report_error=True):
        try:
            self._json_health_warning = self._dashboard_workspace_json_warning()
            self._json_health_error = self._dashboard_json_health_error()
            if self._json_health_error:
                raise RuntimeError(self._json_health_error)
            self._fetch_dashboard_json("/api/status")
            if not self._ensure_trusted():
                raise RuntimeError("workspace trust request failed")
            self._fetch_dashboard_json("/api/sessions")
            self._preflight_error = ""
            return True
        except Exception as exc:
            self._preflight_error = str(exc)
            if report_error:
                self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._preflight_error))
            return False

    def _fetch_dashboard_json(self, path, timeout=2.0):
        if not self.dashboard_url:
            raise RuntimeError("Ant-Code Dashboard URL is empty")
        import urllib.request

        url = f"{self.dashboard_url}{path}"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"{path} returned HTTP {response.status}")
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            preview = body[max(0, exc.pos - 60): exc.pos + 60].replace("\n", "\\n")
            raise RuntimeError(
                f"{path} returned invalid JSON at line {exc.lineno} column {exc.colno}: {preview}"
            ) from exc
        if isinstance(data, dict) and data.get("ok") is False:
            raise RuntimeError(str(data.get("error") or f"{path} failed"))
        return data

    def _on_web_console_message(self, level, message, line_number, source_id):
        text = str(message or "")
        if not text:
            return
        if not self._is_json_console_error(text):
            return
        self._last_console_error = f"{text} ({source_id}:{line_number})"
        if self._is_transient_json_console_error(text):
            self._update_status_label(at("Starting Ant-Code Dashboard...", self.lang))
            if self._pending_context_prompt:
                self._schedule_pending_context_prompt_flush(900)
            return
        if self._pending_context_prompt and self.is_running():
            self._update_status_label(at("Starting Ant-Code Dashboard...", self.lang))
            self._schedule_pending_context_prompt_flush(900)
            return
        self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._last_console_error))

    def _is_json_console_error(self, text):
        lowered = str(text or "").lower()
        patterns = (
            "unexpected end of json input",
            "empty json response",
            "expected double-quoted property name",
            "json.parse",
            "json 解析失败",
        )
        return any(pattern in lowered for pattern in patterns)

    def _is_transient_json_console_error(self, text):
        lowered = str(text or "").lower()
        patterns = (
            "unexpected end of json input",
            "empty json response",
            "expected double-quoted property name",
        )
        return any(pattern in lowered for pattern in patterns)

    def _dashboard_json_health_error(self):
        issue = self._find_invalid_dashboard_json(self._dashboard_context_json_paths())
        if not issue:
            return ""
        return self._format_json_health_issue(self._json_issue_prefix("active_project"), issue)

    def _dashboard_workspace_json_warning(self):
        issue = self._find_invalid_dashboard_json(self._dashboard_workspace_json_paths())
        if not issue:
            return ""
        return self._format_json_health_issue(self._json_issue_prefix("workspace"), issue)

    def _json_issue_prefix(self, kind):
        if self.lang == "zh":
            if kind == "active_project":
                return "当前项目 JSON 检查失败，已阻止 Ant-Code 启动"
            return "工作区中存在无效 JSON 文件"
        if kind == "active_project":
            return "Active project JSON check failed before Ant-Code launch"
        return "Workspace contains an invalid JSON file"

    def _format_json_health_issue(self, prefix, issue):
        rel_path = self._display_json_health_path(issue["path"])
        if self.lang == "zh":
            return (
                f"{prefix}: {rel_path}，第 {issue['line']} 行第 {issue['column']} 列。"
                f"解析器提示：{issue['message']}。"
                f"附近内容：{issue['preview']}"
            )
        return (
            f"{prefix}: "
            f"{rel_path} at line {issue['line']} column {issue['column']}. "
            f"Parser said: {issue['message']}. "
            f"Near: {issue['preview']}"
        )

    def _find_invalid_dashboard_json(self, paths):
        for path in paths:
            if not path.exists() or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8-sig")
                json.loads(text)
            except json.JSONDecodeError as exc:
                return {
                    "path": path,
                    "line": exc.lineno,
                    "column": exc.colno,
                    "message": exc.msg,
                    "preview": self._json_error_preview(text, exc.pos),
                }
            except UnicodeDecodeError as exc:
                return {
                    "path": path,
                    "line": 1,
                    "column": 1,
                    "message": f"cannot decode as UTF-8 JSON ({exc})",
                    "preview": "",
                }
            except OSError:
                continue
        return None

    def _dashboard_context_json_paths(self):
        seen = set()
        yield from self._normalized_json_paths((self._project_display,), seen)
        for key in ("project_path", "review_project_path", "stl_project_path"):
            yield from self._normalized_json_paths((self._context.get(key),), seen)

    def _dashboard_workspace_json_paths(self):
        seen = set()
        root = Path(self.workspace_dir)
        for candidate in sorted(root.glob("*.json")):
            yield from self._normalized_json_paths((candidate,), seen)

    def _normalized_json_paths(self, values, seen):
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            path = Path(text)
            if not path.is_absolute():
                path = Path(self.workspace_dir) / path
            try:
                path = path.resolve()
            except OSError:
                path = path.absolute()
            if path.suffix.lower() != ".json":
                continue
            key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            yield path

    def _display_json_health_path(self, path):
        try:
            return str(path.relative_to(Path(self.workspace_dir)))
        except ValueError:
            return str(path)

    def _json_error_preview(self, text, pos):
        start = max(0, int(pos) - 80)
        end = min(len(text), int(pos) + 80)
        preview = text[start:end].replace("\r", "\\r").replace("\n", "\\n")
        return preview[:180]

    def _send_context_prompt(self, prompt):
        prompt = str(prompt or "")
        if not prompt:
            self._pending_context_prompt = ""
            self._pending_prompt_attempts = 0
            self._browser_context_copied = False
            return
        self._pending_context_prompt = prompt
        if self.browser_mode:
            self._browser_context_copied = self._copy_context_prompt_to_clipboard(prompt)
            if self._browser_context_copied:
                self._pending_context_prompt = ""
                self._pending_prompt_attempts = 0
                self._update_status_label(at("Agent context copied to clipboard. Paste it into the browser prompt.", self.lang))
            if self.is_running() and self.dashboard_url:
                self.open_dashboard_in_browser()
            self._update_fallback()
            return
        if self.is_running() and self.web_view is None:
            self._ensure_web_view()
        if not self.is_running() or self.web_view is None:
            return
        escaped = prompt.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        self.web_view.page().runJavaScript(
            f"""
            (() => {{
              const pageReadyForTaxaMaskPrompt = () => {{
                const project = document.querySelector('#project-path')?.textContent?.trim() || '';
                const send = document.querySelector('#send-button');
                const transcript = document.querySelector('#transcript');
                const trustPanel = document.querySelector('#trust-panel');
                const sendText = send ? send.textContent.trim() : '';
                const panelVisible = trustPanel
                  && !trustPanel.classList.contains('hidden')
                  && trustPanel.textContent.trim().length > 0;
                const loadingProject = ['加载中', 'Loading'].includes(project);
                const trustSendText = ['待信任', 'Trust required'].includes(sendText);
                return Boolean(send && transcript && project && !loadingProject && !trustSendText && !panelVisible);
              }};
              if (!pageReadyForTaxaMaskPrompt()) return false;
              const input = document.querySelector('#prompt-input');
              if (!input) return false;
              input.value = `{escaped}`;
              input.dispatchEvent(new Event('input', {{ bubbles: true }}));
              input.focus();
              return input.value === `{escaped}`;
            }})();
            """,
            lambda ok: self._queue_prompt_if_not_inserted(prompt, ok),
        )

    def _copy_context_prompt_to_clipboard(self, prompt):
        try:
            app = QApplication.instance()
            if app is None:
                return False
            app.clipboard().setText(str(prompt or ""))
            return True
        except Exception:
            return False

    def _queue_prompt_if_not_inserted(self, prompt, ok):
        if ok:
            if self._pending_context_prompt == prompt:
                self._pending_context_prompt = ""
                self._pending_prompt_attempts = 0
            return
        if self._pending_context_prompt != prompt:
            return
        self._pending_prompt_attempts += 1
        delay = min(2500, 300 + self._pending_prompt_attempts * 250)
        self._schedule_pending_context_prompt_flush(delay)

    def _schedule_pending_context_prompt_flush(self, delay_ms=500):
        if not self._pending_context_prompt:
            return
        if self.prompt_retry_timer.isActive():
            return
        self.prompt_retry_timer.start(max(0, int(delay_ms)))

    def _flush_pending_context_prompt(self):
        prompt = self._pending_context_prompt
        if not prompt:
            return
        self._send_context_prompt(prompt)

    def _context_prompt(self, context):
        if not context:
            return ""
        zh_mapping = [
            ("source_workbench", "来源工作台"),
            ("project_type", "项目类型"),
            ("project_path", "项目路径"),
            ("active_specimen_id", "当前 specimen"),
            ("active_volume_scope", "当前体数据范围"),
            ("active_part_id", "当前 part"),
            ("active_part_parent_bbox_zyx", "当前 part 来源 bbox"),
            ("active_image_path", "当前图像"),
            ("active_label_role", "当前标签层"),
            ("selected_part", "当前部位"),
            ("selected_material_id", "当前 material"),
            ("screener_profile", "PDF 筛选方案"),
            ("figure_profile", "PDF 图文提取方案"),
            ("part_description_profile", "PDF 部位描述方案"),
            ("screening_mode", "PDF 筛选模式"),
            ("text_llm_key_configured", "文本 LLM key 已配置"),
            ("text_llm_base_url_configured", "文本 LLM Base URL 已配置"),
            ("text_llm_model", "文本 LLM 模型"),
            ("text_llm_api_protocol", "文本 LLM API 协议"),
            ("multimodal_llm_uses_text_provider", "多模态复用文本模型提供方"),
            ("multimodal_llm_key_configured", "多模态 LLM key 已配置"),
            ("multimodal_llm_base_url_configured", "多模态 LLM Base URL 已配置"),
            ("multimodal_llm_model", "多模态 LLM 模型"),
            ("multimodal_llm_api_protocol", "多模态 LLM API 协议"),
            ("pdf_source_dir", "PDF 源目录"),
            ("screening_output_dir", "PDF 筛选输出目录"),
            ("extract_input_dir", "PDF 提取输入目录"),
            ("extract_result_folder", "PDF 提取结果文件夹"),
            ("extract_db_name", "PDF 提取数据库名"),
            ("extract_db_path", "PDF 提取数据库"),
            ("multimodal_enabled", "多模态复核已启用"),
            ("display_mode", "显示模式"),
            ("active_slice_axis", "当前切片轴"),
            ("active_slice_position", "当前切片位置"),
            ("active_volume_shape_zyx", "当前体数据 shape"),
            ("active_volume_spacing_zyx", "当前体数据 spacing"),
            ("active_label_shape_zyx", "当前标签 shape"),
            ("train_ready_status", "TIF 可训练状态"),
            ("train_ready_reasons", "TIF 不可训练原因"),
            ("active_label_schema_id", "当前标签方案"),
            ("train_ready_part_sample_count", "可训练部位/重切片样本数"),
            ("train_ready_top_level_sample_count", "可训练整只体样本数"),
            ("training_selection_scope", "训练样本选择范围"),
            ("training_sample_rule", "TIF 训练样本规则"),
            ("registered_tif_model_count", "已登记 TIF 模型数"),
            ("selected_tif_model_id", "已选 TIF 模型"),
            ("selected_model_manifest", "已选模型 manifest"),
            ("tif_backend_id", "TIF 后端 ID"),
            ("tif_backend_python", "TIF 后端 Python"),
            ("tif_backend_command_presence", "TIF 后端命令填写状态"),
            ("backend_run_active", "TIF 后台任务运行中"),
            ("backend_action", "TIF 后台动作"),
            ("backend_run_dir", "TIF 后台运行目录"),
            ("backend_result_json", "TIF 后台结果 JSON"),
            ("volume_renderer", "体预览渲染器"),
            ("volume_renderer_label", "体预览渲染器说明"),
            ("volume_render_mode", "体预览交互模式"),
            ("volume_projection_mode", "体预览投影模式"),
            ("volume_mask_mode", "体预览 mask 模式"),
            ("volume_density_cutoff", "体预览密度阈值"),
            ("volume_density_opacity", "体预览透明度"),
            ("volume_texture_target_dim", "体预览纹理目标尺寸"),
            ("volume_ray_samples", "体预览采样数"),
            ("volume_clarity_mode", "体预览清晰模式"),
            ("volume_detail_enhancement", "体预览细节增强"),
            ("volume_tone_curve", "体预览色调曲线"),
            ("volume_shader_quality", "体预览 shader 质量"),
            ("volume_inside_depth", "体内观察深度"),
            ("volume_front_cut", "近端切除"),
            ("volume_zoom", "体预览缩放"),
            ("volume_pan", "体预览平移"),
            ("volume_yaw_pitch", "体预览角度"),
            ("volume_gpu_warning", "体预览 GPU 提示"),
            ("volume_status_overlay", "体预览状态叠加"),
            ("volume_performance_diagnosis", "体预览性能诊断"),
            ("volume_uploaded_shape_zyx", "体预览上传 shape"),
            ("volume_texture_sampling", "体预览纹理采样"),
            ("volume_display_scaling", "体预览显示缩放"),
            ("tif_next_requirement", "TIF 下一步需求"),
            ("tif_requirement_doc", "TIF 需求文档"),
            ("settings_scope", "设置范围"),
            ("settings_question_focus", "需要协助的问题"),
            ("language", "语言"),
            ("theme", "主题"),
            ("startup_behavior", "启动方式"),
            ("project_autosave_interval_sec", "项目自动保存间隔秒数"),
            ("runtime_device", "运行设备"),
            ("model_backend", "2D/STL 模型后端"),
            ("backend_id", "后端 ID"),
            ("display_name", "后端显示名称"),
            ("python_executable", "Python 解释器"),
            ("export_formats", "导出格式"),
            ("external_backend_id", "外部后端 ID"),
            ("external_display_name", "外部后端显示名称"),
            ("external_python", "外部后端 Python"),
            ("prepare_command_present", "数据准备命令已填写"),
            ("train_command_present", "训练命令已填写"),
            ("predict_command_present", "预测命令已填写"),
            ("prepare_command_has_contract", "数据准备命令包含 contract"),
            ("train_command_has_contract", "训练命令包含 contract"),
            ("predict_command_has_contract", "预测命令包含 contract"),
            ("model_manifest_present", "模型 manifest 已填写"),
            ("locator_scope_count", "Locator 主部位数量"),
            ("parent_box_ratio_count", "父级框比例数量"),
            ("validation_errors", "当前校验提示"),
            ("diagnostic_route", "诊断路线"),
            ("diagnostic_focus", "排查重点"),
            ("health_check_summary", "轻量健康检查"),
            ("llm_context_refs", "建议阅读的大模型对接位置"),
            ("source_code_refs", "相关源码/契约位置"),
            ("artifact_hints", "建议检查的产物"),
            ("safety_notes", "安全边界"),
            ("suggested_agent_action", "建议下一步"),
            ("agent_route_source", "路由表来源"),
            ("context_policy", "上下文策略"),
            ("recent_log_excerpt", "最近日志"),
        ]
        en_mapping = [
            ("source_workbench", "Source workbench"),
            ("project_type", "Project type"),
            ("project_path", "Project path"),
            ("active_specimen_id", "Active specimen"),
            ("active_volume_scope", "Active volume scope"),
            ("active_part_id", "Active part"),
            ("active_part_parent_bbox_zyx", "Active part source bbox"),
            ("active_image_path", "Active image"),
            ("active_label_role", "Active label layer"),
            ("selected_part", "Selected structure"),
            ("selected_material_id", "Selected material"),
            ("screener_profile", "PDF screening profile"),
            ("figure_profile", "PDF figure-extraction profile"),
            ("part_description_profile", "PDF part-description profile"),
            ("screening_mode", "PDF screening mode"),
            ("text_llm_key_configured", "Text LLM key configured"),
            ("text_llm_base_url_configured", "Text LLM base URL configured"),
            ("text_llm_model", "Text LLM model"),
            ("text_llm_api_protocol", "Text LLM API protocol"),
            ("multimodal_llm_uses_text_provider", "Multimodal LLM reuses text provider"),
            ("multimodal_llm_key_configured", "Multimodal LLM key configured"),
            ("multimodal_llm_base_url_configured", "Multimodal LLM base URL configured"),
            ("multimodal_llm_model", "Multimodal LLM model"),
            ("multimodal_llm_api_protocol", "Multimodal LLM API protocol"),
            ("pdf_source_dir", "PDF source directory"),
            ("screening_output_dir", "PDF screening output directory"),
            ("extract_input_dir", "PDF extraction input directory"),
            ("extract_result_folder", "PDF extraction result folder"),
            ("extract_db_name", "PDF extraction DB name"),
            ("extract_db_path", "PDF extraction database"),
            ("multimodal_enabled", "Multimodal review enabled"),
            ("display_mode", "Display mode"),
            ("active_slice_axis", "Active slice axis"),
            ("active_slice_position", "Active slice position"),
            ("active_volume_shape_zyx", "Active volume shape"),
            ("active_volume_spacing_zyx", "Active volume spacing"),
            ("active_label_shape_zyx", "Active label shape"),
            ("train_ready_status", "TIF train-ready status"),
            ("train_ready_reasons", "TIF train-ready reasons"),
            ("active_label_schema_id", "Active label schema"),
            ("train_ready_part_sample_count", "Train-ready part/reslice samples"),
            ("train_ready_top_level_sample_count", "Train-ready top-level samples"),
            ("training_selection_scope", "Training sample scope"),
            ("training_sample_rule", "TIF training sample rule"),
            ("registered_tif_model_count", "Registered TIF models"),
            ("selected_tif_model_id", "Selected TIF model"),
            ("selected_model_manifest", "Selected model manifest"),
            ("tif_backend_id", "TIF backend ID"),
            ("tif_backend_python", "TIF backend Python"),
            ("tif_backend_command_presence", "TIF backend command presence"),
            ("backend_run_active", "TIF backend task running"),
            ("backend_action", "TIF backend action"),
            ("backend_run_dir", "TIF backend run directory"),
            ("backend_result_json", "TIF backend result JSON"),
            ("volume_renderer", "Volume renderer"),
            ("volume_renderer_label", "Volume renderer label"),
            ("volume_render_mode", "Volume interaction mode"),
            ("volume_projection_mode", "Volume projection mode"),
            ("volume_mask_mode", "Volume mask mode"),
            ("volume_density_cutoff", "Volume density cutoff"),
            ("volume_density_opacity", "Volume density opacity"),
            ("volume_texture_target_dim", "Volume texture target size"),
            ("volume_ray_samples", "Volume ray samples"),
            ("volume_clarity_mode", "Volume clarity mode"),
            ("volume_detail_enhancement", "Volume detail enhancement"),
            ("volume_tone_curve", "Volume tone curve"),
            ("volume_shader_quality", "Volume shader quality"),
            ("volume_inside_depth", "Volume inside depth"),
            ("volume_front_cut", "Volume front cut"),
            ("volume_zoom", "Volume zoom"),
            ("volume_pan", "Volume pan"),
            ("volume_yaw_pitch", "Volume yaw/pitch"),
            ("volume_gpu_warning", "Volume GPU warning"),
            ("volume_status_overlay", "Volume status overlay"),
            ("volume_performance_diagnosis", "Volume performance diagnosis"),
            ("volume_uploaded_shape_zyx", "Volume uploaded shape"),
            ("volume_texture_sampling", "Volume texture sampling"),
            ("volume_display_scaling", "Volume display scaling"),
            ("tif_next_requirement", "TIF next requirement"),
            ("tif_requirement_doc", "TIF requirement document"),
            ("settings_scope", "Settings scope"),
            ("settings_question_focus", "Question focus"),
            ("language", "Language"),
            ("theme", "Theme"),
            ("startup_behavior", "Startup behavior"),
            ("project_autosave_interval_sec", "Project autosave interval seconds"),
            ("runtime_device", "Runtime device"),
            ("model_backend", "2D/STL model backend"),
            ("backend_id", "Backend ID"),
            ("display_name", "Display name"),
            ("python_executable", "Python executable"),
            ("export_formats", "Export formats"),
            ("external_backend_id", "External backend ID"),
            ("external_display_name", "External display name"),
            ("external_python", "External backend Python"),
            ("prepare_command_present", "Prepare command present"),
            ("train_command_present", "Train command present"),
            ("predict_command_present", "Predict command present"),
            ("prepare_command_has_contract", "Prepare command includes contract"),
            ("train_command_has_contract", "Train command includes contract"),
            ("predict_command_has_contract", "Predict command includes contract"),
            ("model_manifest_present", "Model manifest present"),
            ("locator_scope_count", "Locator structure count"),
            ("parent_box_ratio_count", "Parent box ratio count"),
            ("validation_errors", "Current validation hints"),
            ("diagnostic_route", "Diagnostic route"),
            ("diagnostic_focus", "Diagnostic focus"),
            ("health_check_summary", "Lightweight health check"),
            ("llm_context_refs", "Suggested LLM context references"),
            ("source_code_refs", "Relevant source/contract references"),
            ("artifact_hints", "Suggested artifacts to inspect"),
            ("safety_notes", "Safety boundaries"),
            ("suggested_agent_action", "Suggested next step"),
            ("agent_route_source", "Route table source"),
            ("context_policy", "Context policy"),
            ("recent_log_excerpt", "Recent log excerpt"),
        ]
        if self.lang == "zh":
            lines = ["这是从 TaxaMask 工作台带回来的现场上下文，请先理解现场，不要立即执行高风险动作。"]
            mapping = zh_mapping
        else:
            lines = [
                "This is live context from the TaxaMask workbench. Understand the current research state first; do not take high-risk actions immediately."
            ]
            mapping = en_mapping
        for key, label in mapping:
            value = context.get(key)
            if value:
                lines.append(f"{label}: {value}")
        return "\n".join(lines)

    def open_dashboard_in_browser(self, start_if_needed=True):
        if start_if_needed and not self.is_running():
            self.start_dashboard()
        if not self.dashboard_url:
            return
        try:
            if self._browser_opened_for_url == self.dashboard_url:
                return
            self._browser_opened_for_url = self.dashboard_url
            if self._open_dashboard_with_platform_browser():
                return
            import webbrowser

            webbrowser.open(self.dashboard_url)
        except Exception:
            return

    def _open_dashboard_with_platform_browser(self):
        if not self.dashboard_url:
            return False
        commands = []
        if _is_wsl_runtime():
            commands.extend([
                ["wslview", self.dashboard_url],
                ["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{self.dashboard_url}'"],
                ["cmd.exe", "/c", "start", "", self.dashboard_url],
            ])
        elif sys.platform == "linux":
            commands.append(["xdg-open", self.dashboard_url])
        elif sys.platform == "darwin":
            commands.append(["open", self.dashboard_url])
        for command in commands:
            if shutil.which(command[0]) is None:
                continue
            try:
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=self._creation_flags(),
                )
                return True
            except Exception:
                continue
        return False

    def stop_dashboard(self):
        self.health_timer.stop()
        self.prompt_retry_timer.stop()
        self._request_dashboard_shutdown()
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self._terminate_process_tree(self.process.pid)
                    try:
                        self.process.wait(timeout=2)
                    except Exception:
                        try:
                            self.process.kill()
                        except Exception:
                            pass
            except Exception:
                pass
        self.process = None
        self._close_dashboard_log(remove=True)
        self._cleanup_owned_dashboard_processes()
        self.dashboard_url = ""
        self._update_status_label(at("Ant-Code Dashboard is not running.", self.lang))
        self.stack.setCurrentWidget(self.fallback)
        self._update_fallback()

    def _request_dashboard_shutdown(self):
        if not self.dashboard_url:
            return
        try:
            import urllib.request

            request = urllib.request.Request(f"{self.dashboard_url}/api/shutdown", data=b"{}", method="POST")
            request.add_header("content-type", "application/json")
            urllib.request.urlopen(request, timeout=1.0).read()
        except Exception:
            return

    def _terminate_process_tree(self, pid):
        if not pid:
            return
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=self._creation_flags(),
                )
                return
            except Exception:
                return
        try:
            self.process.terminate()
        except Exception:
            return

    def _cleanup_owned_dashboard_processes(self):
        if sys.platform != "win32":
            return
        for pid in self._owned_dashboard_process_ids():
            self._terminate_process_tree(pid)

    def _owned_dashboard_process_ids(self):
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    "Get-CimInstance Win32_Process | "
                    "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
                check=False,
                creationflags=self._creation_flags(),
            )
        except Exception:
            return []
        if result.returncode != 0 or not str(result.stdout or "").strip():
            return []
        try:
            processes = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        if isinstance(processes, dict):
            processes = [processes]
        owned = []
        current_pid = os.getpid()
        for process in processes or []:
            try:
                pid = int(process.get("ProcessId"))
            except (TypeError, ValueError):
                continue
            if pid == current_pid:
                continue
            if self._is_owned_dashboard_process(process.get("CommandLine"), process.get("Name")):
                owned.append(pid)
        return owned

    def _is_owned_dashboard_process(self, command_line, process_name=""):
        command = self._normalize_process_command(command_line)
        if not command:
            return False
        if self._normalize_process_command(self.workspace_dir) not in command:
            return False
        name = Path(str(process_name or "")).name.lower()
        source_entry = self._normalize_process_command(self.ant_code_dashboard_entry or "")
        source_dashboard = (
            (
                "src\\cli\\dashboard.js" in command
                or ("src\\cli\\index.js" in command and " dashboard " in f" {command} ")
            )
            and (not source_entry or source_entry in command or "src\\cli\\dashboard.js" in command)
            and name in {"node", "node.exe"}
        )
        executable_dashboard = (
            " dashboard " in f" {command} "
            and ("ant-code.exe" in command or "ant-code.cmd" in command or "\\ant-code " in command)
            and (name.startswith("ant-code") or name == "cmd.exe")
        )
        return source_dashboard or executable_dashboard

    def _normalize_process_command(self, value):
        return str(value or "").replace("/", "\\").replace('"', "").lower()

    def closeEvent(self, event):
        self.stop_dashboard()
        self._cleanup_web_profile_storage()
        super().closeEvent(event)

    def _cleanup_web_profile_storage(self):
        self._close_dashboard_log(remove=True)
        path = self._web_profile_storage_dir
        self._web_profile_storage_dir = ""
        if not path:
            return
        try:
            shutil.rmtree(path, ignore_errors=True)
        except Exception:
            return

    def _update_status_label(self, status):
        self._status_text = str(status or "")
        self.status_changed.emit(self._status_text)

    def status_text(self):
        return self._status_text

    def _update_fallback(self):
        lines = []
        if self.browser_mode:
            lines.append("Browser mode is active for this Linux/WSL session. If the dashboard did not open automatically, open the URL below.")
            if self._browser_context_copied:
                lines.append(at("Agent context copied to clipboard. Paste it into the browser prompt.", self.lang))
        elif _QTWEBENGINE_IMPORT_ATTEMPTED and QWebEngineView is None:
            lines.append(at("Qt WebEngine is unavailable in this environment. Start Ant-Code and open it in a browser.", self.lang))
        if self.dashboard_url:
            lines.append(self.dashboard_url)
        if self._preflight_error:
            lines.append(f"Preflight error: {self._preflight_error}")
        if self._embedded_page_error:
            label = "内嵌页面错误" if self.lang == "zh" else "Embedded page error"
            lines.append(f"{label}: {self._embedded_page_error}")
        if self._json_health_warning:
            warning_label = "JSON 提醒（不影响 Ant-Code 启动）" if self.lang == "zh" else "JSON warning (does not block Ant-Code launch)"
            lines.append(f"{warning_label}: {self._json_health_warning}")
        detail = "\n".join(line for line in lines if str(line or "").strip())
        self.fallback_detail.setText(detail)
        self.fallback_detail.setVisible(bool(detail))
