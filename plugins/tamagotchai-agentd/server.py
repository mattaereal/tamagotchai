"""HTTP server: /health, /status, /status/all, /ingest."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from .state import SessionRegistry


def make_handler(registry: SessionRegistry, webhook_backend=None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body=b"", content_type="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_json(self, code, obj):
            self._send(code, json.dumps(obj).encode(), content_type="application/json")

        def do_GET(self):
            if self.path == "/health":
                self._send(200, b"ok")
            elif self.path == "/status":
                self._send_json(200, registry.latest())
            elif self.path == "/status/all":
                self._send_json(200, registry.snapshot_all())
            else:
                self._send(404, b"not found")

        def do_POST(self):
            if self.path == "/ingest" and webhook_backend is not None:
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                code = webhook_backend.handle(body, {k: v for k, v in self.headers.items()})
                self._send(code, b"" if 200 <= code < 300 else b"error")
            else:
                self._send(404, b"not found")

        def log_message(self, *args, **kwargs):
            pass  # quiet; agentd.py wires real logging

    return Handler