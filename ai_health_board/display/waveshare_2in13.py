"""Waveshare 2.13" e-paper display backend."""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from PIL import Image, ImageDraw, ImageFont

from ..display.base import DisplayBackend
from ..models import ComponentStatus, ProviderStatus

logger = logging.getLogger(__name__)

try:
    # Waveshare e-paper SPI library (v2 board)
    from waveshare_epd import epd2in13  # type: ignore
except Exception:
    epd2in13 = None
    logger.warning("waveshare_epd not installed; e-paper hardware will not work")


class Waveshare2in13Display(DisplayBackend):
    """Waveshare 2.13" b/w e-paper display backend."""

    def __init__(self, config: Dict[str, Any]):
        self.width = config.get("width", 250)
        self.height = config.get("height", 122)
        self.rotation = config.get("rotation", 90)
        self._epd = None
        self._img: Image.Image = Image.new("1", (self.width, self.height), 1)
        self._draw = ImageDraw.Draw(self._img)
        self._init_display()

    def _init_display(self) -> None:
        if epd2in13 is None:
            raise RuntimeError("waveshare_epd package not available")
        try:
            self._epd = epd2in13.EPD()
            logger.info("EPD 2in13 init OK")
            self._epd.init()
        except Exception as e:
            logger.error(f"EPD init failed: {e}")
            raise

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def render(self, state: Dict[str, Any]) -> None:
        self._draw.rectangle([0, 0, self.width, self.height], fill=1)
        margin = 6
        line_h = 10
        start_y = 2

        self._draw.text((margin, start_y), "AI HEALTH", fill=0)
        start_y += line_h + 2

        ts = state.get("last_refresh")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                self._draw.text(
                    (margin, start_y), dt.strftime("%Y-%m-%d %H:%M:%S"), fill=0
                )
            except Exception:
                self._draw.text((margin, start_y), str(ts), fill=0)
        start_y += line_h + 4

        providers: List[ProviderStatus] = state.get("providers", [])
        for provider in providers:
            self._draw.text(
                (margin, start_y), f"[{provider.provider_type.upper()}]", fill=0
            )
            self._draw.text(
                (margin + 60, start_y), provider.name, fill=0
            )
            agg = provider.status.icon()
            self._draw.text((margin + 160, start_y), agg, fill=0)
            start_y += line_h

            for comp in provider.components:
                self._draw.text((margin + 10, start_y), comp.status.icon(), fill=0)
                text = f"{comp.name}"
                if len(text) > 30:
                    text = text[:27] + "..."
                self._draw.text((margin + 30, start_y), text, fill=0)
                start_y += line_h

        start_y = self.height - line_h - 2
        footer = "last ok" if state.get("last_refresh") else "no data"
        if state.get("stale"):
            footer += " | STALE"
        self._draw.text((margin, start_y), footer, fill=0)

        if self.rotation in (90, 270):
            self._img = self._img.rotate(self.rotation, expand=1)

        self._push_to_epaper()

    def _push_to_epaper(self) -> None:
        if self._epd is None:
            logger.warning("EPD not initialized, skipping flush")
            return
        try:
            # Convert to monochrome bilevel
            mono = self._img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
            # Rotate if landscape mode expected
            if self.rotation == 90:
                mono = mono.rotate(90, expand=True)
            self._epd.display(self._epd.getbuffer(mono))
            self._epd.sleep()  # Enter deep sleep to preserve power
            logger.debug("EPD frame flushed")
        except Exception as e:
            logger.error(f"EPD flush error: {e}", exc_info=True)

    def flush(self) -> None:
        # For Waveshare, flush is done in render; this is a no-op
        pass
