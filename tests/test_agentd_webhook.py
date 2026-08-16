import hashlib
import hmac
import json
from datetime import datetime, timezone

from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.backends.webhook import WebhookBackend


def _sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(event_name: str, session_id: str = "s1", extra: dict | None = None, tool: str | None = None) -> bytes:
    payload = {
        "hook_event_name": event_name,
        "session_id": session_id,
        "tool_name": tool,
        "tool_input": None,
        "cwd": "/home/u/proj",
        "extra": extra or {},
        "delivery_id": "d1",
        "timestamp": "2026-08-16T10:00:00Z",
    }
    return json.dumps(payload).encode()


def test_map_event_pre_tool_call_returns_working():
    body = _post("pre_tool_call", tool="bash")
    payload = json.loads(body)
    out = WebhookBackend(SessionRegistry(), secret=None).map_event("pre_tool_call", payload)
    assert out is not None
    sid, state = out
    assert sid == "s1"
    assert state["status"] == "working"
    assert state["message"] == "tool: bash"
    assert state["metadata"]["tool_name"] == "bash"


def test_map_event_unknown_returns_none():
    out = WebhookBackend(SessionRegistry(), secret=None).map_event("some_other_event", {"session_id": "s1"})
    assert out is None


def test_handle_valid_signature_updates_registry():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret="shh")
    body = _post("pre_tool_call", tool="bash")
    code = be.handle(body, {"X-Hermes-Signature-256": _sig("shh", body)})
    assert code == 204
    snap = reg.snapshot_all()
    assert len(snap) == 1
    assert snap[0]["status"] == "working"


def test_handle_bad_signature_returns_401():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret="shh")
    body = _post("pre_tool_call", tool="bash")
    code = be.handle(body, {"X-Hermes-Signature-256": "sha256=deadbeef"})
    assert code == 401
    assert reg.snapshot_all() == []


def test_handle_missing_signature_when_secret_set_returns_401():
    be = WebhookBackend(SessionRegistry(), secret="shh")
    body = _post("pre_tool_call")
    assert be.handle(body, {}) == 401


def test_handle_accepts_unsigned_when_no_secret():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret=None)
    body = _post("pre_tool_call", tool="bash")
    assert be.handle(body, {}) == 204
    assert len(reg.snapshot_all()) == 1


def test_handle_malformed_json_returns_400():
    be = WebhookBackend(SessionRegistry(), secret=None)
    assert be.handle(b"{not json", {}) == 400


def test_handle_on_session_end_marks_idle():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret=None)
    body = _post("on_session_end")
    code = be.handle(body, {})
    assert code == 204
    snap = reg.snapshot_all()
    assert snap[0]["status"] == "idle"