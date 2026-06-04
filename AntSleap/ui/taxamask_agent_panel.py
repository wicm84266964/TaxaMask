import os
import json
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path


def _ensure_qtwebengine_cpu_compositing():
    flag = "--disable-gpu-compositing"
    current = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    flags = current.split()
    if flag not in flags:
        flags.append(flag)
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


_ensure_qtwebengine_cpu_compositing()

from PySide6.QtCore import QTimer, QUrl, Signal
from PySide6.QtWidgets import (
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - depends on local Qt installation
    QWebEngineView = None

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineScript
except Exception:  # pragma: no cover - depends on local Qt installation
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineScript = None


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


if QWebEnginePage is not None:
    class TaxaMaskAgentWebPage(QWebEnginePage):
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
else:
    TaxaMaskAgentWebPage = None


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
        self.node_executable = self._resolve_node_executable()
        self.ant_code_dashboard_entry = self._resolve_ant_code_dashboard_entry()
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
        self.setObjectName("taxamaskAgentPanel")
        self.setMinimumWidth(640)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()
        self._apply_style()
        self.set_language(lang)

    def _default_ant_code_root(self):
        repo_root = Path(__file__).resolve().parents[2]
        candidate = repo_root / "vendor" / "ant-code"
        if candidate.exists():
            return candidate
        candidate = repo_root.parent / "lab-agent"
        return candidate

    def _default_ant_code_config_path(self):
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "AntSleap" / "config" / "taxamask_ant_code.config.json"

    def _resolve_node_executable(self):
        env_path = os.environ.get("TAXAMASK_NODE_EXE")
        if env_path and Path(env_path).expanduser().exists():
            return str(Path(env_path).expanduser().resolve())
        for command in ("node.exe", "node"):
            found = shutil.which(command)
            if found:
                return found
        return None

    def _resolve_ant_code_dashboard_entry(self):
        for candidate in (
            Path(self.ant_code_root) / "src" / "cli" / "dashboard.js",
            Path(self.ant_code_root) / "src" / "cli" / "index.js",
        ):
            if candidate.exists():
                return str(candidate.resolve())
        return None

    def _can_use_source_dashboard(self):
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
        command = [
            self.node_executable,
            self.ant_code_dashboard_entry,
        ]
        if Path(self.ant_code_dashboard_entry).name == "index.js":
            command.append("dashboard")
        command.extend([
            "--project",
            self.workspace_dir,
            "--port",
            str(self.port),
            "--no-open",
        ])
        return command

    def _dashboard_environment(self):
        env = os.environ.copy()
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
        self.fallback = QTextEdit()
        self.fallback.setObjectName("taxamaskAgentFallback")
        self.fallback.setReadOnly(True)
        self.fallback.setMinimumHeight(360)
        self.stack.addWidget(self.fallback)
        self.web_view = QWebEngineView() if QWebEngineView is not None else None
        if self.web_view is not None:
            self.web_view.setObjectName("taxamaskAntCodeWebView")
            if TaxaMaskAgentWebPage is not None:
                self.web_view.setPage(TaxaMaskAgentWebPage(self, parent=self.web_view))
            self._configure_web_profile()
            self._install_web_bootstrap_script()
            self.web_view.loadFinished.connect(self._on_web_load_finished)
            self.stack.addWidget(self.web_view)
        root.addWidget(self.stack, 1)

        self.health_timer = QTimer(self)
        self.health_timer.setInterval(500)
        self.health_timer.timeout.connect(self._poll_dashboard_ready)
        self.prompt_retry_timer = QTimer(self)
        self.prompt_retry_timer.setSingleShot(True)
        self.prompt_retry_timer.timeout.connect(self._flush_pending_context_prompt)

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

    def _web_bootstrap_source(self):
        return r"""
(() => {
  if (window.__taxamaskAgentBootstrapInstalled) return;
  window.__taxamaskAgentBootstrapInstalled = true;
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
    if (!document.head || document.querySelector("#taxamask-agent-embed-style")) return;
    document.documentElement.classList.add("taxamask-embed");
    document.body?.classList.add("taxamask-embed-body");
    const style = document.createElement("style");
    style.id = "taxamask-agent-embed-style";
    style.textContent = `
      html,
      body {
        background: #15191d !important;
        overflow: hidden !important;
      }
      .app-shell {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        padding: 0 !important;
      }
      .sidebar,
      .preview {
        display: none !important;
      }
      .workspace {
        border: 0 !important;
        border-radius: 0 !important;
        grid-column: 1 / -1 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        min-width: 0 !important;
        width: 100% !important;
      }
      .workspace-header {
        border-radius: 0 !important;
      }
    `;
    document.head.appendChild(style);
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
"""

    def _apply_style(self):
        self.setStyleSheet(
            """
            QWidget#taxamaskAgentPanel {
                background: #1A1F24;
                border: 1px solid #364149;
                border-radius: 16px;
            }
            QTextEdit#taxamaskAgentFallback {
                background: #11161A;
                border: 1px solid #303A42;
                border-radius: 12px;
                color: #DCE4E8;
                padding: 10px;
            }
            QStackedWidget#taxamaskAgentStack {
                background: transparent;
                border: none;
            }
            """
        )

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
            self.process = subprocess.Popen(
                command,
                cwd=self.workspace_dir,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=self._creation_flags(),
            )
        except Exception as exc:
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

    def _creation_flags(self):
        if sys.platform != "win32":
            return 0
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def _poll_dashboard_ready(self):
        if not self.is_running():
            self.health_timer.stop()
            self._update_status_label(at("Ant-Code process exited.", self.lang))
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
        self._update_status_label(at("Ant-Code Dashboard is ready.", self.lang))
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
        if self.web_view is None:
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
        self.stack.setCurrentWidget(self.web_view)
        cache_key = f"taxamask_embed=1&reload={self._load_retries}"
        self.web_view.load(QUrl(f"{self.dashboard_url}/?{cache_key}"))

    def _web_post_load_source(self):
        return r"""
            (() => {
              const applyTaxaMaskDefaults = () => {
                const workspaceButton = document.querySelector('#permission-mode button[data-mode="workspace"]');
                if (workspaceButton && !workspaceButton.classList.contains('active')) {
                  workspaceButton.click();
                }
                const localLabel = document.querySelector('.workspace-local span:last-child');
                if (localLabel) localLabel.textContent = 'TaxaMask Agent · 源码只读保护已启用';
                const brand = document.querySelector('.brand-name');
                if (brand) brand.textContent = 'TaxaMask Agent';
                const subtitle = document.querySelector('.brand-subtitle');
                if (subtitle) subtitle.textContent = 'Ant-Code native';
                const emptyKicker = document.querySelector('.empty-kicker');
                if (emptyKicker) emptyKicker.textContent = 'TaxaMask Agent';
                const emptyTitle = document.querySelector('.empty-title');
                if (emptyTitle) emptyTitle.textContent = '我会在当前 TaxaMask 仓库中协助排查';
                const emptyCopy = document.querySelector('.empty-copy');
                if (emptyCopy) emptyCopy.textContent = '可以读源码和排查配置；外部模型适配和 TaxaMask 源码开发会分别请求确认。';
                const prompt = document.querySelector('#prompt-input');
                if (prompt) prompt.placeholder = '把遇到的问题、配置目标或标注流程疑问发给 TaxaMask Agent';
              };
              const trustPending = () => {
                const send = document.querySelector('#send-button');
                const trustPanel = document.querySelector('#trust-panel');
                const sendText = send ? send.textContent.trim() : '';
                const panelVisible = trustPanel
                  && !trustPanel.classList.contains('hidden')
                  && trustPanel.textContent.trim().length > 0;
                return sendText === '待信任' || Boolean(panelVisible);
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
              void reconcileTrust();
            })();
            """

    def _on_web_load_finished(self, ok):
        if self.web_view is None:
            return
        if not ok:
            self._embedded_page_error = "embedded page load failed"
            self._update_status_label(at("Unable to start Ant-Code: {0}", self.lang).format(self._embedded_page_error))
            self.stack.setCurrentWidget(self.fallback)
            self._update_fallback()
            return
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
              return Boolean(send && transcript && project && project !== '加载中' && sendText !== '待信任' && !panelVisible);
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
        for key in ("project_path", "review_project_path", "tif_project_path", "stl_project_path"):
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
            return
        self._pending_context_prompt = prompt
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
                return Boolean(send && transcript && project && project !== '加载中' && sendText !== '待信任' && !panelVisible);
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
        lines = [
            "这是从 TaxaMask 工作台带回来的现场上下文，请先理解现场，不要立即执行高风险动作。",
        ]
        mapping = [
            ("source_workbench", "来源工作台"),
            ("project_type", "项目类型"),
            ("project_path", "项目路径"),
            ("active_specimen_id", "当前 specimen"),
            ("active_image_path", "当前图像"),
            ("active_label_role", "当前标签层"),
            ("selected_part", "当前部位"),
            ("selected_material_id", "当前 material"),
            ("screener_profile", "PDF 筛选方案"),
            ("figure_profile", "PDF 图文提取方案"),
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
            ("extract_db_path", "PDF 提取数据库"),
            ("multimodal_enabled", "多模态复核已启用"),
            ("settings_scope", "设置范围"),
            ("settings_question_focus", "需要协助的问题"),
            ("language", "语言"),
            ("theme", "主题"),
            ("startup_behavior", "启动方式"),
            ("project_autosave_interval_sec", "项目自动保存间隔秒数"),
            ("runtime_device", "运行设备"),
            ("model_backend", "2D/STL 模型后端"),
            ("backend_id", "TIF 后端 ID"),
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
        for key, label in mapping:
            value = context.get(key)
            if value:
                lines.append(f"{label}: {value}")
        return "\n".join(lines)

    def open_dashboard_in_browser(self):
        if not self.is_running():
            self.start_dashboard()
        if not self.dashboard_url:
            return
        try:
            import webbrowser

            webbrowser.open(self.dashboard_url)
        except Exception:
            return

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
        lines = [
            at("Ant-Code embedded", self.lang),
            "",
            f"{at('Project', self.lang)}: {self._project_display or self.workspace_dir}",
            f"Ant-Code root: {self.ant_code_root}",
            f"Ant-Code dashboard: {self.ant_code_dashboard_entry or at('not found', self.lang)}",
            f"Ant-Code config: {self.ant_code_config_path}",
            "",
            at("Workspace permission is the default for this embedded TaxaMask agent.", self.lang),
            "TaxaMask source guard: enabled",
        ]
        if QWebEngineView is None:
            lines.extend(["", at("Qt WebEngine is unavailable in this environment. Start Ant-Code and open it in a browser.", self.lang)])
        if self.dashboard_url:
            lines.extend(["", self.dashboard_url])
        if self._preflight_error:
            lines.extend(["", f"Preflight error: {self._preflight_error}"])
        if self._embedded_page_error:
            label = "内嵌页面错误" if self.lang == "zh" else "Embedded page error"
            lines.extend(["", f"{label}: {self._embedded_page_error}"])
        if self._json_health_warning:
            warning_label = "JSON 提醒（不影响 Ant-Code 启动）" if self.lang == "zh" else "JSON warning (does not block Ant-Code launch)"
            lines.extend(["", f"{warning_label}: {self._json_health_warning}"])
        self.fallback.setPlainText("\n".join(lines))
