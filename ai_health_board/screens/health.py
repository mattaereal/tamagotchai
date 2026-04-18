"""AI health status screen (portrait layout)."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw

from .base import Screen
from ..models import AppState, ServiceStatus, ProviderStatus, ComponentStatus
from ..providers import get_provider
from ..config import ProviderConfig
from ..cache import load_cache, save_cache

logger = logging.getLogger(__name__)

_STATUS_ICONS = {
    "OK": "[+]",
    "DEGRADED": "[!]",
    "DOWN": "[-]",
    "UNKNOWN": "[?]",
}


def _make_anthropic_icon() -> Image.Image:
    """12x12 1-bit Anthropic starburst icon."""
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    c = [
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
    ]
    for x, y in c:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


def _make_openai_icon() -> Image.Image:
    """12x12 1-bit OpenAI hexagonal knot icon."""
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    c = [
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
    ]
    for x, y in c:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


def _make_lotus_icon() -> Image.Image:
    """12x12 1-bit lotus flower icon."""
    img = Image.new("1", (12, 12), 255)
    d = ImageDraw.Draw(img)
    c = [
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
    ]
    for x, y in c:
        if 0 <= x < 12 and 0 <= y < 12:
            d.point((x, y), fill=0)
    return img


_PROVIDER_ICONS: Dict[str, Image.Image] = {}


def _get_provider_icon(provider_type: str) -> Optional[Image.Image]:
    """Get a cached pixel art icon for a provider type."""
    if not _PROVIDER_ICONS:
        _PROVIDER_ICONS["statuspage_anthropic"] = _make_anthropic_icon()
        _PROVIDER_ICONS["statuspage_openai"] = _make_openai_icon()
        _PROVIDER_ICONS["lotus_health"] = _make_lotus_icon()
        _PROVIDER_ICONS["lotus_stats"] = _make_lotus_icon()
    return _PROVIDER_ICONS.get(provider_type)


def _resolve_icon_key(provider_name: str, provider_type: str) -> str:
    """Resolve which icon to use based on provider name and type."""
    name_lower = provider_name.lower()
    if "claude" in name_lower or "anthropic" in name_lower:
        return "statuspage_anthropic"
    if "openai" in name_lower or "gpt" in name_lower:
        return "statuspage_openai"
    if "lotus" in name_lower:
        return "lotus_health"
    return provider_type


class HealthScreen(Screen):
    """Screen showing AI service health status in portrait layout."""

    def __init__(
        self,
        providers: List[ProviderConfig],
        poll_interval: int = 30,
        display_duration: int = 30,
    ):
        self._provider_configs = providers
        self._poll_interval = poll_interval
        self._display_duration = display_duration
        self._state: Optional[AppState] = None
        self._last_render_hash: Optional[str] = None

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    def _display_name_for(
        self, comp_name: str, provider_config: Optional[ProviderConfig]
    ) -> str:
        """Resolve a component's display name using provider display_names mapping."""
        if provider_config and provider_config.display_names:
            mapped = provider_config.display_names.get(comp_name)
            if mapped:
                return mapped
        return comp_name

    def _provider_config_for(self, provider_name: str) -> Optional[ProviderConfig]:
        """Find the ProviderConfig matching a provider name."""
        for pc in self._provider_configs:
            if pc.name == provider_name:
                return pc
        return None

    async def fetch(self, session: Any) -> None:
        providers = []
        for pc in self._provider_configs:
            try:
                provider = get_provider(pc)
                providers.append(provider)
            except Exception as e:
                logger.error(f"Failed to create provider {pc.name}: {e}")

        tasks = [p.get_status(session) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved: List[Optional[ProviderStatus]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Provider fetch failed: {r}")
                resolved.append(None)
            else:
                resolved.append(r)

        cache = load_cache() or {}
        state = AppState(
            last_refresh=datetime.now(timezone.utc),
            providers=[r for r in resolved if r is not None],
            stale=False,
        )

        if cache and "providers" in cache:
            cached_provs = {p["name"]: p for p in cache["providers"]}
            for prov in state.providers:
                if prov.name in cached_provs:
                    cached = cached_provs[prov.name]
                    cached_map = {
                        c["name"]: c["status"] for c in cached.get("components", [])
                    }
                    for comp in prov.components:
                        if (
                            comp.status == ServiceStatus.UNKNOWN
                            and comp.name in cached_map
                        ):
                            comp.status = ServiceStatus(cached_map[comp.name])
                            comp.failure_count = cached.get("consecutive_failures", 0)

        save_cache(state.to_dict())
        self._state = state

    def render(self, width: int, height: int) -> Image.Image:
        img = Image.new("1", (width, height), 255)
        draw = ImageDraw.Draw(img)
        margin = 4
        line_h = 12
        y = 4

        draw.text((margin, y), "AI HEALTH", fill=0)
        y += line_h + 2

        if self._state and self._state.last_refresh:
            ts = self._state.last_refresh.strftime("%H:%M:%S")
            draw.text((margin, y), ts, fill=0)
        y += line_h + 2

        draw.line([(margin, y), (width - margin, y)], fill=0)
        y += 4

        if self._state:
            for prov in self._state.providers:
                if y + line_h > height - 14:
                    draw.text((margin, y), "...", fill=0)
                    break

                pc = self._provider_config_for(prov.name)
                icon_key = _resolve_icon_key(prov.name, prov.provider_type)
                icon_img = _get_provider_icon(icon_key)
                if icon_img:
                    img.paste(icon_img, (margin, y))
                    draw.text((margin + 16, y), prov.name, fill=0)
                else:
                    pstatus = prov.status.value
                    agg_icon = _STATUS_ICONS.get(pstatus, "[?]")
                    draw.text((margin, y), agg_icon, fill=0)
                    draw.text((margin + 26, y), prov.name, fill=0)
                y += line_h

                for comp in prov.components:
                    if y + line_h > height - 14:
                        break
                    cicon = _STATUS_ICONS.get(comp.status.value, "[?]")
                    display_name = self._display_name_for(comp.name, pc)
                    if len(display_name) > 14:
                        display_name = display_name[:11] + "..."
                    draw.text((margin + 8, y), cicon, fill=0)
                    draw.text((margin + 28, y), display_name, fill=0)
                    y += line_h

        footer_y = height - line_h - 2
        footer = "ok" if self._state and self._state.last_refresh else "no data"
        if self._state and self._state.stale:
            footer += " | STALE"
        draw.text((margin, footer_y), footer, fill=0)

        self._last_render_hash = self._state_hash()
        return img

    def has_changed(self) -> bool:
        if self._last_render_hash is None:
            return True
        return self._state_hash() != self._last_render_hash

    def _state_hash(self) -> str:
        if self._state is None:
            return ""
        return str(self._state.to_dict())
