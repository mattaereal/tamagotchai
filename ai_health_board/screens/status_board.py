"""Generic status board screen (template: status_board).

Displays categories with items, each showing a status icon.
Supports two category types:
- statuspage/lotus_health: uses provider normalization
- json: fetches raw JSON and maps item keys to statuses via convention
"""

import asyncio
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

logger = logging.getLogger(__name__)

_STATUS_ICONS = {
    "OK": "[+]",
    "DEGRADED": "[!]",
    "DOWN": "[-]",
    "UNKNOWN": "[?]",
}

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
    """Map a JSON value to ServiceStatus using convention."""
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


def _make_anthropic_icon() -> Image.Image:
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (5, 0),
        (6, 0),
        (5, 1),
        (6, 1),
        (4, 3),
        (7, 3),
        (4, 4),
        (7, 4),
        (5, 5),
        (6, 5),
        (2, 4),
        (3, 5),
        (8, 5),
        (9, 4),
        (2, 7),
        (3, 6),
        (8, 6),
        (9, 7),
        (5, 7),
        (6, 7),
        (5, 8),
        (6, 8),
        (5, 10),
        (6, 10),
        (5, 11),
        (6, 11),
        (0, 5),
        (1, 6),
        (10, 6),
        (11, 5),
    ]:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


def _make_openai_icon() -> Image.Image:
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (3, 0),
        (4, 0),
        (7, 0),
        (8, 0),
        (2, 1),
        (5, 1),
        (6, 1),
        (9, 1),
        (1, 2),
        (4, 2),
        (7, 2),
        (10, 2),
        (0, 3),
        (3, 3),
        (8, 3),
        (11, 3),
        (0, 4),
        (5, 4),
        (6, 4),
        (11, 4),
        (1, 5),
        (4, 5),
        (7, 5),
        (10, 5),
        (1, 6),
        (4, 6),
        (7, 6),
        (10, 6),
        (0, 7),
        (5, 7),
        (6, 7),
        (11, 7),
        (0, 8),
        (3, 8),
        (8, 8),
        (11, 8),
        (1, 9),
        (4, 9),
        (7, 9),
        (10, 9),
        (2, 10),
        (5, 10),
        (6, 10),
        (9, 10),
        (3, 11),
        (4, 11),
        (7, 11),
        (8, 11),
    ]:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


def _make_lotus_icon() -> Image.Image:
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (5, 0),
        (6, 0),
        (4, 1),
        (5, 1),
        (6, 1),
        (7, 1),
        (3, 2),
        (4, 2),
        (7, 2),
        (8, 2),
        (2, 3),
        (3, 3),
        (8, 3),
        (9, 3),
        (1, 4),
        (2, 4),
        (9, 4),
        (10, 4),
        (1, 5),
        (2, 5),
        (5, 5),
        (6, 5),
        (9, 5),
        (10, 5),
        (2, 6),
        (3, 6),
        (5, 6),
        (6, 6),
        (8, 6),
        (9, 6),
        (3, 7),
        (4, 7),
        (7, 7),
        (8, 7),
        (4, 8),
        (5, 8),
        (6, 8),
        (7, 8),
        (3, 9),
        (4, 9),
        (7, 9),
        (8, 9),
        (2, 10),
        (3, 10),
        (8, 10),
        (9, 10),
        (1, 11),
        (2, 11),
        (9, 11),
        (10, 11),
    ]:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


def _make_generic_icon() -> Image.Image:
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 9, 9], outline=0, width=1)
    d.point((5, 5), fill=0)
    return img


_BUILTIN_ICONS: Dict[str, Image.Image] = {}


def _get_icon(icon_name: str) -> Optional[Image.Image]:
    if not _BUILTIN_ICONS:
        _BUILTIN_ICONS["anthropic"] = _make_anthropic_icon()
        _BUILTIN_ICONS["openai"] = _make_openai_icon()
        _BUILTIN_ICONS["lotus"] = _make_lotus_icon()
        _BUILTIN_ICONS["generic"] = _make_generic_icon()

    if icon_name in _BUILTIN_ICONS:
        return _BUILTIN_ICONS[icon_name]

    if icon_name.endswith(".png") and os.path.exists(icon_name):
        try:
            img = Image.open(icon_name).convert("L")
            resized = img.resize((12, 12), Image.LANCZOS)
            return resized.convert("1", dither=Image.FLOYDSTEINBERG)
        except Exception as e:
            logger.warning(f"Failed to load icon {icon_name}: {e}")

    return _BUILTIN_ICONS.get("generic")


def _resolve_icon_key(category_name: str, category_type: str) -> str:
    name_lower = category_name.lower()
    if "claude" in name_lower or "anthropic" in name_lower:
        return "anthropic"
    if "openai" in name_lower or "gpt" in name_lower:
        return "openai"
    if "lotus" in name_lower:
        return "lotus"
    return category_type


class CategoryData:
    def __init__(self, name: str, icon_key: str, items: Dict[str, ServiceStatus]):
        self.name = name
        self.icon_key = icon_key
        self.items = items

    def hash_str(self) -> str:
        parts = [f"{k}:{v.value}" for k, v in sorted(self.items.items())]
        return f"{self.name}|{self.icon_key}|{'|'.join(parts)}"


class StatusBoardScreen(Screen):
    """Generic status board screen driven by category config."""

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
            cat.icon if cat.icon != "generic" else _resolve_icon_key(cat.name, cat.type)
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
            cat.icon if cat.icon != "generic" else _resolve_icon_key(cat.name, cat.type)
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
                        else _resolve_icon_key(cat.name, cat.type)
                    )
                    items = {item.label: ServiceStatus.UNKNOWN for item in cat.items}
                    categories.append(
                        CategoryData(name=cat.name, icon_key=icon_key, items=items)
                    )

        self._categories = categories
        self._last_refresh = datetime.now(timezone.utc)

    def render(self, width: int, height: int) -> Image.Image:
        img = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(img)
        margin = 4
        line_h = 12
        y = 4

        draw.text((margin, y), self._config.name, fill=0)
        y += line_h + 2

        if self._last_refresh:
            ts = self._last_refresh.strftime("%H:%M:%S")
            draw.text((margin, y), ts, fill=0)
        y += line_h + 2

        draw.line([(margin, y), (width - margin, y)], fill=0)
        y += 4

        for cat in self._categories:
            if y + line_h > height - 14:
                draw.text((margin, y), "...", fill=0)
                break

            icon_img = _get_icon(cat.icon_key)
            if icon_img:
                img.paste(icon_img, (margin, y))
                draw.text((margin + 16, y), cat.name, fill=0)
            else:
                draw.text((margin, y), cat.name, fill=0)
            y += line_h

            for label, status in cat.items.items():
                if y + line_h > height - 14:
                    break
                cicon = _STATUS_ICONS.get(status.value, "[?]")
                display_label = label
                if len(display_label) > 14:
                    display_label = display_label[:11] + "..."
                draw.text((margin + 8, y), cicon, fill=0)
                draw.text((margin + 28, y), display_label, fill=0)
                y += line_h

        footer_y = height - line_h - 2
        footer = "ok" if self._last_refresh else "no data"
        draw.text((margin, footer_y), footer, fill=0)

        self._last_render_hash = self._hash()
        return img

    def has_changed(self) -> bool:
        if self._last_render_hash is None:
            return True
        return self._hash() != self._last_render_hash

    def _hash(self) -> str:
        parts = [c.hash_str() for c in self._categories]
        ts = self._last_refresh.isoformat() if self._last_refresh else ""
        return f"{ts}|{'||'.join(parts)}"
