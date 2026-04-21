"""Generic tamagotchi screen (type: tamagotchi).

Config-driven sprites, mood mapping, and info lines.
Fetches raw JSON from a single url, extracts values using
dot-notation key paths via resolve_key().
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig, resolve_key
from ui.assets import load_sprite
from ui.formatters import auto_format

logger = logging.getLogger(__name__)

_SPRITE_W = 90
_SPRITE_H = 90


class TamagotchiScreen(Screen):
    def __init__(self, config: ScreenConfig):
        self._config = config
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._data: Dict[str, Any] = {}
        self._last_render_data_hash: Optional[str] = None
        self._mood: str = "idle"
        self._frame: int = 0

        self._sprites: Dict[str, Image.Image] = {}
        if config.sprites:
            for mood_key in ("idle", "working", "error", "success"):
                path = getattr(config.sprites, mood_key, "")
                sprite = load_sprite(path) if path else None
                if sprite:
                    self._sprites[mood_key] = sprite
                    logger.debug(f"Loaded sprite for {mood_key}: {path}")

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def fetch(self, session: Any) -> None:
        import aiohttp

        try:
            resp = await session.get(
                self._config.url, timeout=aiohttp.ClientTimeout(total=10)
            )
            resp.raise_for_status()
            data = await resp.json()
            if not isinstance(data, dict):
                data = {"value": data}
        except Exception as e:
            logger.warning(f"Fetch failed for {self._config.name}: {e}")
            data = {"__fetch_error": True}

        data["__last_checked"] = datetime.now(timezone.utc).isoformat()
        self._data = data
        self._resolve_mood()

        stale_threshold = self._config.stale_threshold
        heartbeat = self._data.get("last_heartbeat")
        if heartbeat:
            try:
                dt = datetime.fromisoformat(heartbeat)
                age = (datetime.now(timezone.utc) - dt).total_seconds()
                if age > stale_threshold:
                    self._data["status"] = "offline"
                    self._resolve_mood()
            except (ValueError, TypeError):
                pass

    def _resolve_mood(self) -> None:
        mm = self._config.mood_map
        if not mm:
            self._mood = "idle"
            return

        field_val = str(resolve_key(self._data, mm.key, "")).lower()

        if mm.map:
            self._mood = mm.map.get(field_val, mm.fallback)
            return

        pending = resolve_key(self._data, "pending", 0)

        if field_val == "ok":
            if pending and int(pending) > 0:
                self._mood = mm.ok_busy
            else:
                self._mood = mm.ok
        else:
            self._mood = mm.error

    def render(self, width: int, height: int) -> Image.Image:
        from ui.layouts import render as tpl_render
        from ui.canvas import Canvas

        info_lines = []
        if self._data.get("__fetch_error"):
            pass
        else:
            for il in self._config.info_lines:
                value = self._format_info_line(il)
                if il.max_length and len(value) > il.max_length:
                    value = value[: il.max_length - 3] + "..."
                info_lines.append({"label": il.label, "value": value})

        data = {
            "name": self._config.name,
            "mood": self._mood,
            "frame": self._frame,
            "sprites": self._sprites,
            "info_lines": info_lines,
            "fetch_error": bool(self._data.get("__fetch_error")),
            "last_checked": self._data.get("__last_checked", ""),
        }

        self._frame = (self._frame + 1) % max(len(self._sprites), 1)
        self._last_render_data_hash = self._data_hash()
        return tpl_render("tamagotchi", data, canvas=Canvas(width, height))

    def _format_info_line(self, il) -> str:
        if il.template and il.keys:
            try:
                vals = [resolve_key(self._data, k, "?") for k in il.keys]
                formatted = [auto_format(il.label, v) for v in vals]
                return il.template.format(*formatted)
            except (KeyError, IndexError):
                return "?"
        if il.key:
            val = resolve_key(self._data, il.key, "")
            return auto_format(il.label, val)
        return ""

    def has_changed(self) -> bool:
        if self._last_render_data_hash is None:
            return True
        return self._data_hash() != self._last_render_data_hash

    def _data_hash(self) -> str:
        return str(sorted(self._data.items()))
