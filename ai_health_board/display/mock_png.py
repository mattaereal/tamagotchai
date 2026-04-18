"""Mock display backend that writes PNG files."""
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont

from ..display.base import DisplayBackend
from ..models import ComponentStatus, ProviderStatus

logger = logging.getLogger(__name__)


class MockPNGDisplay(DisplayBackend):
    """Renders status to a local PNG file (useful for testing on laptops)."""

    def __init__(self, config: Dict[str, Any]):
        self._width = config.get("width", 250)
        self._height = config.get("height", 122)
        self.rotation = config.get("rotation", 90)
        self._img: Image.Image = Image.new("1", (self._width, self._height), 1)
        self._draw = ImageDraw.Draw(self._img)
        self._out_dir = "out"
        os.makedirs(self._out_dir, exist_ok=True)
        logger.info(f"MockPNGDisplay initialized {self._width}x{self._height}")

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
        # Monochrome fill
        self._draw.rectangle([0, 0, self._width, self._height], fill=1)
        margin = 6
        line_h = 10
        start_y = 2
        col_x = margin

        self._draw.text((col_x, start_y), "AI HEALTH", fill=0)
        start_y += line_h + 2

        ts = state.get("last_refresh")
        if ts:
            try:
                dt = datetime.fromisoformat(
                    ts.replace("Z", "+00:00")
                )
                self._draw.text(
                    (col_x, start_y), dt.strftime("%Y-%m-%d %H:%M:%S"), fill=0
                )
            except Exception:
                self._draw.text((col_x, start_y), str(ts), fill=0)
        start_y += line_h + 4

        providers: List[ProviderStatus] = state.get("providers", [])
        for provider in providers:
            self._draw.text((col_x, start_y), f"[{provider.provider_type.upper()}]", fill=0)
            self._draw.text(
                (col_x + 60, start_y), provider.name, fill=0
            )
            agg = provider.status.icon()
            self._draw.text((col_x + 160, start_y), agg, fill=0)
            start_y += line_h

            for comp in provider.components:
                self._draw.text((col_x + 10, start_y), comp.status.icon(), fill=0)
                text = f"{comp.name}"
                if len(text) > 30:
                    text = text[:27] + "..."
                self._draw.text((col_x + 30, start_y), text, fill=0)
                start_y += line_h

        start_y = self._height - line_h - 2
        last = state.get("last_refresh")
        stale = state.get("stale", False)
        footer = "last ok" if last else "no data"
        if stale:
            footer += " | STALE"
        self._draw.text((col_x, start_y), footer, fill=0)

        if self.rotation in (90, 270):
            self._img = self._img.rotate(self.rotation, expand=1)

    def flush(self) -> None:
        tmp_path = os.path.join(self._out_dir, "frame.png.tmp")
        final_path = os.path.join(self._out_dir, "frame.png")
        self._img.save(tmp_path, format="PNG")
        os.replace(tmp_path, final_path)
        logger.debug("Mock PNG written to out/frame.png")
