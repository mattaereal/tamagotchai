"""Waveshare 2.13" G e-paper display backend (4-color, 122x250).

Four-color display: black/white/yellow/red. No partial refresh support.
Uses display(image) with a 4-level grayscale image.

Resolution: 122x250.
"""

import logging
import time
from typing import Any, Dict, Union

from PIL import Image, ImageDraw

from .base import DisplayBackend
from ..config import DisplayConfig

logger = logging.getLogger(__name__)

try:
    from waveshare_epd import epd2in13g  # type: ignore
except Exception:
    epd2in13g = None


class Waveshare2in13GDisplay(DisplayBackend):
    """Waveshare 2.13\" G (4-color) e-paper display backend. Full refresh only."""

    def __init__(self, config: Union[DisplayConfig, Dict[str, Any]]):
        self._epd = None
        self._init_display()
        self._width = self._epd.width
        self._height = self._epd.height
        self._img: Image.Image = Image.new("1", (self._width, self._height), 255)
        self._draw = ImageDraw.Draw(self._img)
        logger.info(f"Waveshare2in13G initialized: {self._width}x{self._height}")

    def _init_display(self) -> None:
        if epd2in13g is None:
            raise RuntimeError(
                "waveshare_epd.epd2in13g not available. "
                "Install the Waveshare e-Paper library."
            )
        try:
            self._epd = epd2in13g.EPD()
            self._epd.init()
            self._epd.Clear()
            logger.info("EPD 2in13 G init OK")
        except Exception as e:
            logger.error(f"EPD init failed: {e}")
            raise

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
        self._push_to_epaper()

    def render_image(self, img: Image.Image) -> None:
        if self._epd is None:
            return
        try:
            buf = self._epd.getbuffer(img)
            self._epd.display(buf)
            time.sleep(2)
            logger.debug("EPD full refresh (4-color, B/W only)")
        except Exception as e:
            logger.error(f"EPD render_image error: {e}", exc_info=True)

    def _push_to_epaper(self) -> None:
        if self._epd is None:
            return
        try:
            buf = self._epd.getbuffer(self._img)
            self._epd.display(buf)
            time.sleep(2)
        except Exception as e:
            logger.error(f"EPD flush error: {e}", exc_info=True)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self._epd is not None:
            try:
                self._epd.sleep()
                logger.info("EPD sleep OK")
            except Exception as e:
                logger.error(f"EPD sleep error: {e}")
            self._epd = None
