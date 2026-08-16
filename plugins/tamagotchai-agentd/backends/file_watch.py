"""File backend: polls ~/.pi/agent/tamagotchai/sessions/*.json into the registry."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..state import SessionRegistry

logger = logging.getLogger(__name__)


class FileWatchBackend:
    def __init__(self, registry: SessionRegistry, sessions_dir: str) -> None:
        self._registry = registry
        self._dir = Path(sessions_dir)
        self._seen: set[str] = set()

    def poll(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        present_ids: set[str] = set()
        for p in self._dir.glob("*.json"):
            try:
                payload = json.loads(p.read_text())
                if not isinstance(payload, dict):
                    logger.warning("ignoring non-object file %s", p)
                    continue
                sid = payload.get("session_id") or p.stem
                self._registry.update(sid, payload)
                present_ids.add(sid)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("malformed session file %s: %s", p, e)
                continue
        for sid in self._seen - present_ids:
            self._registry.remove(sid)
        self._seen = present_ids