"""OpenCode detail screen (template: opencode).

Dedicated single-agent screen that shows ALL metadata from
opencode-plugin-tamagotchai in a dense vertical layout.

Fetches from /status (latest active session).
If fetch fails, the template renders a compact hint instead.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig

logger = logging.getLogger(__name__)


class OpenCodeScreen(Screen):
    def __init__(self, config: ScreenConfig):
        self._config = config
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._data: Dict[str, Any] = {}
        self._last_hash: Optional[str] = None

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def fetch(self, session: Any) -> None:
        import aiohttp

        url = self._config.url or "http://127.0.0.1:7788/status"
        try:
            resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
            resp.raise_for_status()
            data = await resp.json()
            if not isinstance(data, dict):
                data = {"value": data}
            self._data = data
        except Exception as e:
            logger.warning(f"Fetch failed for {self._config.name}: {e}")
            self._data = {"__fetch_error": True}

    def render(self, width: int, height: int) -> Image.Image:
        from ui.templates import render as tpl_render
        from ui.canvas import Canvas

        data = {
            "name": self._config.name,
            "status": self._data.get("status", ""),
            "message": self._data.get("message", ""),
            "last_heartbeat": self._data.get("last_heartbeat", ""),
            "pending": self._data.get("pending", 0),
            "metadata": self._data.get("metadata") if isinstance(self._data.get("metadata"), dict) else {},
            "fetch_error": bool(self._data.get("__fetch_error")),
        }

        self._last_hash = self._data_hash()
        return tpl_render("opencode", data, canvas=Canvas(width, height))

    def has_changed(self) -> bool:
        if self._last_hash is None:
            return True
        return self._data_hash() != self._last_hash

    def _data_hash(self) -> str:
        raw = str(sorted(self._data.items()))
        return hashlib.md5(raw.encode()).hexdigest()
