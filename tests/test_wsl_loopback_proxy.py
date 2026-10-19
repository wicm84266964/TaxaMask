import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import unittest

from AntSleap.ui.wsl_loopback_proxy import start_wsl_loopback_proxy


class _EchoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path, "auth": self.headers.get("Authorization", "")}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


class WslLoopbackProxyTest(unittest.TestCase):
    def test_proxy_forwards_only_windows_loopback(self):
        origin = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
        origin_thread = threading.Thread(target=origin.serve_forever, daemon=True)
        origin_thread.start()
        proxy = start_wsl_loopback_proxy("127.0.0.1")
        try:
            opener = build_opener(ProxyHandler({"http": proxy.url}))
            response = opener.open(
                Request(
                    f"http://127.0.0.1:{origin.server_address[1]}/v1/models",
                    headers={"Authorization": "Bearer test-key"},
                ),
                timeout=5,
            )
            payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(payload["path"], "/v1/models")
            self.assertEqual(payload["auth"], "Bearer test-key")

            with self.assertRaises(HTTPError) as denied:
                opener.open(Request("http://example.invalid/v1/models"), timeout=5)
            self.assertEqual(denied.exception.code, 403)
        finally:
            proxy.stop()
            origin.shutdown()
            origin.server_close()


if __name__ == "__main__":
    unittest.main()
