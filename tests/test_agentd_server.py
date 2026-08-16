import json
from http.server import HTTPServer
from threading import Thread
from urllib import request

from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.server import make_handler


def _start_server(registry, webhook_backend=None):
    handler = make_handler(registry, webhook_backend)
    srv = HTTPServer(("127.0.0.1", 0), handler)
    Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _get(port, path):
    with request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read().decode()


def test_health_returns_200_ok():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/health")
    srv.shutdown()
    assert body == "ok"


def test_status_returns_idle_when_empty():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/status")
    srv.shutdown()
    data = json.loads(body)
    assert data["status"] == "idle"
    assert data["message"] == "no sessions"


def test_status_all_returns_array():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/status/all")
    srv.shutdown()
    assert json.loads(body) == []


def test_status_all_returns_registered_sessions():
    from datetime import datetime, timezone
    reg = SessionRegistry()
    now = datetime(2026, 8, 16, 10, 5, 0, tzinfo=timezone.utc)
    reg.update("s1", {"status": "working", "last_heartbeat": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "metadata": {}})
    srv = _start_server(reg)
    _, body = _get(srv.server_address[1], "/status/all")
    srv.shutdown()
    arr = json.loads(body)
    assert len(arr) == 1
    assert arr[0]["session_id"] == "s1"


def test_unknown_path_returns_404():
    srv = _start_server(SessionRegistry())
    try:
        _get(srv.server_address[1], "/nope")
    except request.HTTPError as e:
        assert e.code == 404
    srv.shutdown()


def test_ingest_returns_404_without_webhook_backend():
    srv = _start_server(SessionRegistry())
    try:
        req = request.Request(f"http://127.0.0.1:{srv.server_address[1]}/ingest", method="POST")
        request.urlopen(req, timeout=5)
    except request.HTTPError as e:
        assert e.code == 404
    srv.shutdown()