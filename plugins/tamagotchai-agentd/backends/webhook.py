"""Webhook backend: /ingest receiver with HMAC-SHA256 verify + hermes event map."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from ..state import SessionRegistry

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Per-session accumulated counters (tokens/cost/tools). In-memory; rebuilt on restart.
_acc: dict[str, dict] = {}


def _acc_init(sid: str) -> dict:
    return _acc.setdefault(sid, {
        "tokens_input": 0, "tokens_output": 0, "tokens_total": 0,
        "cost_usd": 0.0, "tools_executed": 0, "subagents_done": 0,
        "model": None, "project": None,
    })


class WebhookBackend:
    def __init__(self, registry: SessionRegistry, secret: Optional[str]) -> None:
        self._registry = registry
        self._secret = secret

    def map_event(self, event_name: str, payload: dict) -> Optional[Tuple[str, dict]]:
        sid = payload.get("session_id")
        if not sid:
            return None
        tool = payload.get("tool_name")
        extra = payload.get("extra") or {}
        cwd = payload.get("cwd") or ""
        acc = _acc_init(sid)
        if cwd:
            acc["project"] = cwd.rsplit("/", 1)[-1] or cwd

        def base(status: str, message: str) -> dict:
            return {
                "status": status,
                "message": message,
                "last_heartbeat": _now_iso(),
                "pending": 1 if status == "working" else 0,
                "metadata": {
                    "source": "hermes",
                    "project": acc["project"],
                    "model": acc.get("model"),
                    "tool_name": tool,
                    "tokens_input": acc["tokens_input"],
                    "tokens_output": acc["tokens_output"],
                    "tokens_total": acc["tokens_total"],
                    "cost_usd": round(acc["cost_usd"], 4),
                    "tools_executed": acc["tools_executed"],
                    "subagents_done": acc["subagents_done"],
                },
            }

        if event_name in ("on_session_start", "session_start"):
            return sid, base("working", "session started")
        if event_name == "pre_tool_call":
            return sid, base("working", f"tool: {tool}" if tool else "tool: ?")
        if event_name == "post_tool_call":
            acc["tools_executed"] += 1
            err = bool(extra.get("error") or extra.get("is_error"))
            status = "error" if err else "success"
            return sid, base(status, f"tool: {tool}" if tool else "tool: ?")
        if event_name in ("on_message", "message_end"):
            u = extra.get("usage") or {}
            if isinstance(u, dict):
                acc["tokens_input"] += int(u.get("input", 0) or 0)
                acc["tokens_output"] += int(u.get("output", 0) or 0)
                acc["tokens_total"] += int(u.get("totalTokens", 0) or 0)
                cost = u.get("cost")
                if isinstance(cost, dict):
                    acc["cost_usd"] += float(cost.get("total", 0) or 0)
            m = extra.get("model")
            if m:
                acc["model"] = m
            return sid, base("working", "")
        if event_name == "on_session_end":
            return sid, base("idle", "ended")
        if event_name == "subagent_stop":
            acc["subagents_done"] += 1
            return sid, base("working", "")
        return None

    def _verify(self, body: bytes, headers: dict) -> bool:
        if not self._secret:
            return True  # dev mode: unsigned accepted
        sig = headers.get("X-Hermes-Signature-256") or headers.get("x-hermes-signature-256")
        if not sig:
            return False
        expected = "sha256=" + hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def handle(self, body: bytes, headers: dict) -> int:
        if self._secret and not self._verify(body, headers):
            return 401
        try:
            payload = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400
        if not isinstance(payload, dict):
            return 400
        event_name = payload.get("hook_event_name") or payload.get("type")
        if not event_name:
            return 400
        mapped = self.map_event(event_name, payload)
        if mapped is None:
            return 204  # event observed, no state change
        sid, state = mapped
        self._registry.update(sid, state)
        return 204