"""OpenCode detail screen (template: opencode).

Dedicated single-agent screen. Users configure info_lines in
screens.yml to choose which fields appear. All dot-notation keys
are supported (e.g. metadata.model, metadata.cost_usd).

If fetch fails, the template renders a setup hint instead.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig, resolve_key

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

        info_lines = []
        if not self._data.get("__fetch_error"):
            for il in self._config.info_lines:
                value = self._format_info_line(il)
                if il.max_length and len(value) > il.max_length:
                    value = value[: il.max_length - 3] + "..."
                info_lines.append({"label": il.label, "value": value})

        data = {
            "name": self._config.name,
            "status": self._data.get("status", ""),
            "message": self._data.get("message", ""),
            "last_heartbeat": self._data.get("last_heartbeat", ""),
            "pending": self._data.get("pending", 0),
            "fetch_error": bool(self._data.get("__fetch_error")),
            "info_lines": info_lines,
        }

        self._last_hash = self._data_hash()
        return tpl_render("opencode", data, canvas=Canvas(width, height))

    def _format_info_line(self, il) -> str:
        if il.template and il.keys:
            try:
                vals = [str(resolve_key(self._data, k, "?")) for k in il.keys]
                return il.template.format(*vals)
            except (KeyError, IndexError):
                return "?"
        if il.key:
            val = resolve_key(self._data, il.key, "")
            return str(val)
        return ""

    def has_changed(self) -> bool:
        if self._last_hash is None:
            return True
        return self._data_hash() != self._last_hash

    def _data_hash(self) -> str:
        raw = str(sorted(self._data.items()))
        return hashlib.md5(raw.encode()).hexdigest()
