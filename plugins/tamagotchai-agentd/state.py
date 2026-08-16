"""In-memory session registry with stale sweep. Owns staleness for the display."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def _parse_heartbeat(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _Entry:
    session_id: str
    payload: dict = field(default_factory=dict)
    heartbeat: Optional[datetime] = None


class SessionRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, _Entry] = {}

    def update(self, session_id: str, payload: dict) -> None:
        hb = _parse_heartbeat(payload.get("last_heartbeat", ""))
        self._entries[session_id] = _Entry(
            session_id=session_id,
            payload=dict(payload),
            heartbeat=hb,
        )
        self._entries[session_id].payload["session_id"] = session_id

    def remove(self, session_id: str) -> None:
        self._entries.pop(session_id, None)

    def sweep(self, stale_secs: int, now: datetime) -> None:
        stale_at = now - timedelta(seconds=stale_secs)
        dead_at = now - timedelta(seconds=2 * stale_secs)
        for sid, e in list(self._entries.items()):
            if e.heartbeat is None:
                continue
            if e.heartbeat < dead_at:
                self._entries.pop(sid, None)
            elif e.heartbeat < stale_at:
                e.payload["status"] = "offline"

    def snapshot_all(self) -> List[dict]:
        live = [e for e in self._entries.values() if e.heartbeat is not None]
        live.sort(key=lambda e: e.heartbeat, reverse=True)
        return [dict(e.payload) for e in live]

    def latest(self) -> dict:
        snap = self.snapshot_all()
        if snap:
            return snap[0]
        return {
            "status": "idle",
            "message": "no sessions",
            "last_heartbeat": _now_iso(),
            "pending": 0,
            "metadata": {},
        }
