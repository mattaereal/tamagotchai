"""UiTemplateScreen - wraps a ui/ template as a Screen instance.

Allows any registered ui/ template to participate in the screen-cycling
scheduler. Use template names like 'ui:boot', 'ui:error', 'ui:idle' etc.
in config YAML.

Data can be provided statically via ScreenConfig or fetched from a url
as raw JSON (same pattern as tamagotchi's json fetch).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig, resolve_key
from ui.canvas import Canvas
from ui.templates import get as get_template, names as template_names

logger = logging.getLogger(__name__)


class UiTemplateScreen(Screen):
    """Screen backed by a ui/ template function."""

    def __init__(self, config: ScreenConfig, template_name: str):
        self._config = config
        self._template_name = template_name
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._data: Dict[str, Any] = {}
        self._static_data: Dict[str, Any] = {}
        self._last_data_hash: Optional[str] = None

        if config.url:
            self._fetch_mode = "json"
        else:
            self._fetch_mode = "static"
            self._data = self._build_static_data(config)

    @staticmethod
    def _build_static_data(config: ScreenConfig) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": config.name}
        if config.info_lines:
            info = []
            for il in config.info_lines:
                entry: Dict[str, str] = {}
                if il.label:
                    entry["label"] = il.label
                if il.key:
                    entry["value"] = il.key
                if il.template:
                    entry["value"] = il.template
                if entry:
                    info.append(entry)
            if info:
                d["info"] = info
        if config.mood_map:
            d["mood"] = config.mood_map.ok
        return d

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def fetch(self, session: Any) -> None:
        if self._fetch_mode == "static":
            return

        try:
            import aiohttp

            resp = await session.get(
                self._config.url, timeout=aiohttp.ClientTimeout(total=10)
            )
            resp.raise_for_status()
            data = await resp.json()
            if not isinstance(data, dict):
                data = {"value": data}
        except Exception as e:
            logger.warning(f"Fetch failed for ui:{self._template_name}: {e}")
            data = {"__fetch_error": True, "message": str(e)}

        data["__last_checked"] = datetime.now(timezone.utc).isoformat()
        self._data = data

    def render(self, width: int, height: int) -> Image.Image:
        c = Canvas(width, height)
        render_fn = get_template(self._template_name)
        img = render_fn(c, self._data)
        self._last_data_hash = self._data_hash()
        return img

    def has_changed(self) -> bool:
        if self._last_data_hash is None:
            return True
        return self._data_hash() != self._last_data_hash

    def _data_hash(self) -> str:
        raw = str(sorted(self._data.items()))
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    def is_ui_template(template_name: str) -> bool:
        if template_name.startswith("ui:"):
            return True
        core = {"status_board", "tamagotchi"}
        return template_name not in core and template_name in template_names()

    @staticmethod
    def strip_prefix(template_name: str) -> str:
        if template_name.startswith("ui:"):
            return template_name[3:]
        return template_name
