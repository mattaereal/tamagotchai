"""Generic status board screen (template: status_board).

Displays categories with items, each showing a status icon.
Supports two category types:
- statuspage: uses provider normalization
- json: fetches raw JSON and maps item keys to statuses via convention
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from .base import Screen
from ..config import ScreenConfig, StatusBoardCategory, resolve_key
from ..models import ServiceStatus, ComponentStatus, ProviderStatus
from ..providers import get_provider
from ..cache import load_cache, save_cache
from ui.canvas import Canvas
from ui import layout, MARGIN
from ui.assets import get_icon, resolve_icon_key

logger = logging.getLogger(__name__)

_JSON_STATUS_MAP = {
    "ok": ServiceStatus.OK,
    "up": ServiceStatus.OK,
    "operational": ServiceStatus.OK,
    "healthy": ServiceStatus.OK,
    "true": ServiceStatus.OK,
    "degraded": ServiceStatus.DEGRADED,
    "warning": ServiceStatus.DEGRADED,
    "partial": ServiceStatus.DEGRADED,
    "down": ServiceStatus.DOWN,
    "error": ServiceStatus.DOWN,
    "false": ServiceStatus.DOWN,
    "outage": ServiceStatus.DOWN,
    "offline": ServiceStatus.DOWN,
}


def _json_value_to_status(val: Any) -> ServiceStatus:
    if val is None:
        return ServiceStatus.UNKNOWN
    if isinstance(val, bool):
        return ServiceStatus.OK if val else ServiceStatus.DOWN
    if isinstance(val, (int, float)):
        return ServiceStatus.OK if val == 0 else ServiceStatus.DEGRADED
    if isinstance(val, str):
        return _JSON_STATUS_MAP.get(val.lower(), ServiceStatus.UNKNOWN)
    if isinstance(val, dict):
        s = val.get("status", val.get("state", ""))
        return _JSON_STATUS_MAP.get(str(s).lower(), ServiceStatus.UNKNOWN)
    return ServiceStatus.UNKNOWN


class CategoryData:
    def __init__(self, name: str, icon_key: str, items: Dict[str, ServiceStatus]):
        self.name = name
        self.icon_key = icon_key
        self.items = items

    def hash_str(self) -> str:
        parts = [f"{k}:{v.value}" for k, v in sorted(self.items.items())]
        return f"{self.name}|{self.icon_key}|{'|'.join(parts)}"


class StatusBoardScreen(Screen):
    def __init__(self, config: ScreenConfig):
        self._config = config
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._categories: List[CategoryData] = []
        self._last_render_hash: Optional[str] = None
        self._last_refresh: Optional[datetime] = None

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def _fetch_json(self, session: Any, url: str) -> Dict[str, Any]:
        import aiohttp

        resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
        resp.raise_for_status()
        return await resp.json()

    async def _fetch_provider_category(
        self, session: Any, cat: StatusBoardCategory
    ) -> CategoryData:
        icon_key = (
            cat.icon if cat.icon != "generic" else resolve_icon_key(cat.name, cat.type)
        )
        items: Dict[str, ServiceStatus] = {}

        from ..config import ProviderConfig

        pc = ProviderConfig(
            name=cat.name,
            type=cat.type,
            url=cat.url,
            components=[item.key for item in cat.items],
        )
        provider = get_provider(pc)
        result = await provider.get_status(session)

        comp_map = {c.name: c for c in result.components}
        for item in cat.items:
            if item.key in comp_map:
                items[item.label] = comp_map[item.key].status
            else:
                items[item.label] = ServiceStatus.UNKNOWN

        return CategoryData(name=cat.name, icon_key=icon_key, items=items)

    async def _fetch_json_category(
        self, session: Any, cat: StatusBoardCategory
    ) -> CategoryData:
        icon_key = (
            cat.icon if cat.icon != "generic" else resolve_icon_key(cat.name, cat.type)
        )
        items: Dict[str, ServiceStatus] = {}

        try:
            data = await self._fetch_json(session, cat.url)
            for item in cat.items:
                val = resolve_key(data, item.key)
                items[item.label] = _json_value_to_status(val)
        except Exception as e:
            logger.warning(f"Fetch failed for json category {cat.name}: {e}")
            for item in cat.items:
                items[item.label] = ServiceStatus.UNKNOWN

        return CategoryData(name=cat.name, icon_key=icon_key, items=items)

    async def fetch(self, session: Any) -> None:
        categories: List[CategoryData] = []

        for cat in self._config.categories:
            if cat.type == "json":
                categories.append(await self._fetch_json_category(session, cat))
            else:
                try:
                    categories.append(await self._fetch_provider_category(session, cat))
                except Exception as e:
                    logger.warning(f"Fetch failed for category {cat.name}: {e}")
                    icon_key = (
                        cat.icon
                        if cat.icon != "generic"
                        else resolve_icon_key(cat.name, cat.type)
                    )
                    items = {item.label: ServiceStatus.UNKNOWN for item in cat.items}
                    categories.append(
                        CategoryData(name=cat.name, icon_key=icon_key, items=items)
                    )

        self._categories = categories
        self._last_refresh = datetime.now(timezone.utc)

    def render(self, width: int, height: int) -> Image.Image:
        c = Canvas(width, height)
        timestamp = (
            self._last_refresh.strftime("%H:%M:%S") if self._last_refresh else ""
        )
        y = layout.header(c, self._config.name, MARGIN, timestamp)

        for cat in self._categories:
            if layout.is_overflow(y, c.h):
                y = layout.overflow_marker(c, y)
                break

            icon_img = get_icon(cat.icon_key)
            y = layout.category_row(c, cat.name, icon_img, y)

            for label, status in cat.items.items():
                if layout.is_overflow(y, c.h):
                    break
                y = layout.item_row(c, label, status.value, y)

        footer_text = "ok" if self._last_refresh else "no data"
        layout.footer(c, footer_text)

        self._last_render_hash = self._hash()
        return c.to_image()

    def has_changed(self) -> bool:
        if self._last_render_hash is None:
            return True
        return self._hash() != self._last_render_hash

    def _hash(self) -> str:
        parts = [c.hash_str() for c in self._categories]
        ts = self._last_refresh.isoformat() if self._last_refresh else ""
        return f"{ts}|{'||'.join(parts)}"
