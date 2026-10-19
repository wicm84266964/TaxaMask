"""Let the WSL embedded agent reach a gateway that only listens on Windows loopback.

WSL has its own 127.0.0.1. A gateway bound to Windows 127.0.0.1 is invisible there.
This proxy runs on the Windows address WSL already uses to reach the host, and it
only forwards requests whose target is a loopback host.
"""

from __future__ import annotations

import select
import socket
import threading
from urllib.parse import urlsplit

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
_HOP_BY_HOP = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "proxy-connection",
})


class WslLoopbackProxy:
    def __init__(self, bind_host: str, port: int = 0):
        self.bind_host = bind_host
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((bind_host, int(port)))
        self._server.listen(32)
        self._server.settimeout(0.5)
        self.port = int(self._server.getsockname()[1])
        self.url = f"http://{bind_host}:{self.port}"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept_loop, name="taxamask-wsl-loopback-proxy", daemon=True)

    def start(self) -> str:
        self._thread.start()
        return self.url

    def stop(self) -> None:
        self._stop.set()
        try:
            self._server.close()
        except OSError:
            pass
        self._thread.join(timeout=2)

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                client, _address = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=_handle_client, args=(client,), daemon=True).start()


def start_wsl_loopback_proxy(bind_host: str) -> WslLoopbackProxy:
    proxy = WslLoopbackProxy(bind_host)
    proxy.start()
    return proxy


def _handle_client(client: socket.socket) -> None:
    try:
        client.settimeout(20)
        header = b""
        while b"\r\n\r\n" not in header and len(header) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                return
            header += chunk
        head, _, rest = header.partition(b"\r\n\r\n")
        lines = head.decode("iso-8859-1", errors="replace").split("\r\n")
        if not lines or len(lines[0].split(" ", 2)) < 2:
            return
        method, target, *_version = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
        if method.upper() == "CONNECT":
            _tunnel(client, target)
            return
        _forward_http(client, method, target, headers, rest)
    except Exception:
        try:
            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        except OSError:
            pass
    finally:
        try:
            client.close()
        except OSError:
            pass


def _tunnel(client: socket.socket, target: str) -> None:
    host, port = _split_host_port(target, 443)
    if not _is_loopback(host):
        client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        return
    try:
        upstream = socket.create_connection((_dial_host(host), port), timeout=20)
    except OSError:
        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        return
    client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    client.settimeout(None)
    upstream.settimeout(None)
    _pipe(client, upstream)


def _forward_http(client: socket.socket, method: str, target: str, headers: dict[str, str], already: bytes) -> None:
    parts = urlsplit(target)
    host = parts.hostname or ""
    if not _is_loopback(host):
        client.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        return
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    length = int(headers.get("Content-Length") or headers.get("content-length") or "0")
    body = already
    while len(body) < length:
        chunk = client.recv(min(65536, length - len(body)))
        if not chunk:
            break
        body += chunk
    request_headers = {
        key: value for key, value in headers.items()
        if key.lower() not in _HOP_BY_HOP and key.lower() != "host"
    }
    request_headers["Host"] = host if port in {80, 443} else f"{host}:{port}"
    request_headers["Connection"] = "close"
    raw_headers = "".join(f"{key}: {value}\r\n" for key, value in request_headers.items())
    payload = f"{method} {path} HTTP/1.1\r\n{raw_headers}\r\n".encode("iso-8859-1", errors="replace") + body[:length]
    try:
        upstream = socket.create_connection((_dial_host(host), port), timeout=20)
    except OSError:
        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        return
    try:
        upstream.sendall(payload)
        while True:
            chunk = upstream.recv(65536)
            if not chunk:
                break
            client.sendall(chunk)
    finally:
        upstream.close()


def _pipe(left: socket.socket, right: socket.socket) -> None:
    sockets = [left, right]
    try:
        while sockets:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                break
            for sock in readable:
                other = right if sock is left else left
                chunk = sock.recv(65536)
                if not chunk:
                    return
                other.sendall(chunk)
    except OSError:
        return
    finally:
        right.close()


def _split_host_port(target: str, default_port: int) -> tuple[str, int]:
    if target.startswith("["):
        host, _, port_text = target[1:].partition("]")
        port_text = port_text[1:] if port_text.startswith(":") else ""
    else:
        host, _, port_text = target.rpartition(":")
        if not _:
            host, port_text = target, ""
    return host, int(port_text or default_port)


def _is_loopback(host: str) -> bool:
    return host.strip().lower() in LOOPBACK_HOSTS


def _dial_host(host: str) -> str:
    lowered = host.strip().lower()
    if lowered == "localhost":
        return "127.0.0.1"
    if lowered == "[::1]":
        return "::1"
    return host
