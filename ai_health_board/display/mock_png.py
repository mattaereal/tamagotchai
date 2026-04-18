"""Mock display backend that writes PNG files.

Portrait mode: images at (122, 250) matching EPD native dims.
PNG output saved in portrait orientation.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw

from ..display.base import DisplayBackend
from ..config import DisplayConfig

logger = logging.getLogger(__name__)

_STATUS_ICONS = {
    "OK": "[+]",
    "DEGRADED": "[!]",
    "DOWN": "[-]",
    "UNKNOWN": "[?]",
}


def _get_display_value(
    config: Union[DisplayConfig, Dict[str, Any]], key: str, default: Any
) -> Any:
    if isinstance(config, DisplayConfig):
        return getattr(config, key, default)
    return config.get(key, default)


def _norm_providers(raw: List[Any]) -> List[Dict[str, Any]]:
    result = []
    for p in raw:
        if isinstance(p, dict):
            result.append(p)
        else:
            result.append(p.to_dict())
    return result


class MockPNGDisplay(DisplayBackend):
    """Renders status to a local PNG file (useful for testing on laptops)."""

    def __init__(self, config: Union[DisplayConfig, Dict[str, Any]]):
        self._width = _get_display_value(config, "width", 122)
        self._height = _get_display_value(config, "height", 250)
        self._img: Image.Image = Image.new("1", (self._width, self._height), 255)
        self._draw = ImageDraw.Draw(self._img)
        self._out_dir = "out"
        os.makedirs(self._out_dir, exist_ok=True)
        logger.info(
            f"MockPNGDisplay initialized (portrait {self._width}x{self._height})"
        )

    @property
    def size(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def render(self, state: Dict[str, Any]) -> None:
        self._draw.rectangle([0, 0, self._width, self._height], fill=255)
        margin = 4
        line_h = 12
        y = 4

        self._draw.text((margin, y), "AI HEALTH", fill=0)
        y += line_h + 2

        ts = state.get("last_refresh")
        if ts:
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = ts
                self._draw.text((margin, y), dt.strftime("%H:%M:%S"), fill=0)
            except Exception:
                self._draw.text((margin, y), str(ts), fill=0)
        y += line_h + 2

        self._draw.line([(margin, y), (self._width - margin, y)], fill=0)
        y += 4

        providers = _norm_providers(state.get("providers", []))
        for provider in providers:
            if y + line_h > self._height - 14:
                self._draw.text((margin, y), "...", fill=0)
                break
            ptype = provider.get("provider_type", "?").upper()
            pname = provider.get("name", "?")
            pstatus = provider.get("status", "UNKNOWN")
            agg_icon = _STATUS_ICONS.get(pstatus, "[?]")
            if len(pname) > 12:
                pname = pname[:9] + "..."
            self._draw.text((margin, y), agg_icon, fill=0)
            self._draw.text((margin + 26, y), pname, fill=0)
            y += line_h

            for comp in provider.get("components", []):
                if y + line_h > self._height - 14:
                    break
                if isinstance(comp, dict):
                    cstatus = comp.get("status", "UNKNOWN")
                    cname = comp.get("name", "?")
                else:
                    cstatus = comp.status.value
                    cname = comp.name
                comp_icon = _STATUS_ICONS.get(cstatus, "[?]")
                text = str(cname)
                if len(text) > 14:
                    text = text[:11] + "..."
                self._draw.text((margin + 8, y), comp_icon, fill=0)
                self._draw.text((margin + 30, y), text, fill=0)
                y += line_h

        footer_y = self._height - line_h - 2
        footer = "ok" if state.get("last_refresh") else "no data"
        if state.get("stale"):
            footer += " | STALE"
        self._draw.text((margin, footer_y), footer, fill=0)

        self._save_png()

    def render_image(self, img: Image.Image) -> None:
        """Save a PIL Image as PNG."""
        self._img = img
        self._draw = ImageDraw.Draw(self._img)
        self._save_png()

    def _save_png(self) -> None:
        tmp_path = os.path.join(self._out_dir, "frame.png.tmp")
        final_path = os.path.join(self._out_dir, "frame.png")
        self._img.save(tmp_path, format="PNG")
        os.replace(tmp_path, final_path)
        logger.debug("Mock PNG written to out/frame.png")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass
