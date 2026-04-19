"""Generic tamagotchi screen (template: tamagotchi).

Config-driven sprites, mood mapping, and info lines.
Fetches raw JSON from a single url, extracts values using
dot-notation key paths via resolve_key().
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from .base import Screen
from ..config import ScreenConfig, resolve_key
from ui.canvas import Canvas
from ui import layout, MARGIN
from ui.assets import load_sprite

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

    def _resolve_mood(self) -> None:
        mm = self._config.mood_map
        if not mm:
            self._mood = "idle"
            return

        field_val = str(resolve_key(self._data, mm.key, "")).lower()
        pending = resolve_key(self._data, "pending", 0)

        if field_val == "ok":
            if pending and int(pending) > 0:
                self._mood = mm.ok_busy
            else:
                self._mood = mm.ok
        else:
            self._mood = mm.error

    def render(self, width: int, height: int) -> Image.Image:
        c = Canvas(width, height)

        c.text((MARGIN, 3), self._config.name, fill=0)
        c.hline(14, fill=0)

        sprite_y = 18
        sprite = self._sprites.get(self._mood)
        if not sprite:
            available = list(self._sprites.values())
            if available:
                sprite = available[self._frame % len(available)]

        if sprite:
            sx = (c.w - _SPRITE_W) // 2
            c.paste(sprite, (sx, sprite_y))
        else:
            _draw_fallback_face(c, self._mood, sprite_y, self._frame)

        self._frame = (self._frame + 1) % max(len(self._sprites), 1)

        text_y = sprite_y + _SPRITE_H + 6

        if self._data.get("__fetch_error"):
            c.text((MARGIN, text_y), "[-] connection error", fill=0)
        else:
            for il in self._config.info_lines:
                if text_y + layout.LINE_H_SMALL > height - layout.FOOTER_RESERVE:
                    break

                value = self._format_info_line(il)
                if il.max_length and len(value) > il.max_length:
                    value = value[: il.max_length - 3] + "..."
                label = il.label
                text = f"{label}: {value}" if label else value
                c.text((MARGIN, text_y), text, fill=0)
                text_y += layout.LINE_H_SMALL

        footer_y = height - layout.LINE_H - 2
        last_checked = self._data.get("__last_checked", "")
        if last_checked:
            try:
                dt = datetime.fromisoformat(last_checked)
                ts = dt.strftime("%H:%M:%S")
                c.text((MARGIN, footer_y), f"{self._mood} | {ts}", fill=0)
            except (ValueError, TypeError):
                c.text((MARGIN, footer_y), f"mood: {self._mood}", fill=0)
        else:
            c.text((MARGIN, footer_y), f"mood: {self._mood}", fill=0)

        self._last_render_data_hash = self._data_hash()
        return c.to_image()

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
        if self._last_render_data_hash is None:
            return True
        return self._data_hash() != self._last_render_data_hash

    def _data_hash(self) -> str:
        return str(sorted(self._data.items()))


def _draw_fallback_face(c: Canvas, mood: str, top_y: int, frame: int) -> None:
    cx = c.w // 2
    cy = top_y + _SPRITE_H // 2
    face_r = 28
    eye_y = cy - 8
    left_eye_x = cx - 10
    right_eye_x = cx + 10

    c.ellipse([cx - face_r, cy - face_r, cx + face_r, cy + face_r], outline=0, width=1)

    if frame % 2 == 1 and mood != "error":
        c.line([(left_eye_x - 3, eye_y), (left_eye_x + 3, eye_y)], fill=0, width=1)
        c.line([(right_eye_x - 3, eye_y), (right_eye_x + 3, eye_y)], fill=0, width=1)
    else:
        c.ellipse([left_eye_x - 3, eye_y - 3, left_eye_x + 3, eye_y + 3], fill=0)
        c.ellipse([right_eye_x - 3, eye_y - 3, right_eye_x + 3, eye_y + 3], fill=0)

    mouth_y = cy + 10
    if mood == "idle":
        c.arc(
            [cx - 8, mouth_y - 4, cx + 8, mouth_y + 6],
            start=0,
            end=180,
            fill=0,
            width=1,
        )
    elif mood == "working":
        c.line([(cx - 6, mouth_y), (cx + 6, mouth_y)], fill=0, width=1)
    else:
        c.arc(
            [cx - 8, mouth_y, cx + 8, mouth_y + 10], start=180, end=360, fill=0, width=1
        )
