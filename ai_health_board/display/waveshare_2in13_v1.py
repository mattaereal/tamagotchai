"""Waveshare 2.13" V1 e-paper display backend.

V1 uses a different partial refresh API than V2/V3/V4:
  - Must re-init with partial LUT before each partial update
  - No displayPartial() method -- uses display() after init(PART_UPDATE)
  - Full refresh via init(FULL_UPDATE) + display()

Resolution: 122x250, B/W, supports partial refresh.
"""

import logging
import time
from typing import Any, Dict, Union

from PIL import Image, ImageDraw

from .base import DisplayBackend
from ..config import DisplayConfig

logger = logging.getLogger(__name__)

try:
    from waveshare_epd import epd2in13  # type: ignore
except Exception:
    epd2in13 = None


def _get_display_value(
    config: Union[DisplayConfig, Dict[str, Any]], key: str, default: Any
) -> Any:
    if isinstance(config, DisplayConfig):
        return getattr(config, key, default)
    return config.get(key, default)


class Waveshare2in13V1Display(DisplayBackend):
    """Waveshare 2.13" V1 b/w e-paper display backend."""

    def __init__(self, config: Union[DisplayConfig, Dict[str, Any]]):
        self._epd = None
        self._update_count = 0
        self._base_set = False
        self._full_refresh_every = _get_display_value(
            config, "full_refresh_every_n_updates", 50
        )
        self._init_display()
        self._width = self._epd.width
        self._height = self._epd.height
        self._img: Image.Image = Image.new("1", (self._width, self._height), 255)
        self._draw = ImageDraw.Draw(self._img)
        logger.info(
            f"Waveshare2in13V1 initialized: portrait {self._width}x{self._height}"
        )

    def _init_display(self) -> None:
        if epd2in13 is None:
            raise RuntimeError(
                "waveshare_epd.epd2in13 not available. "
                "Install the Waveshare e-Paper library."
            )
        try:
            self._epd = epd2in13.EPD()
            self._epd.init(self._epd.FULL_UPDATE)
            self._epd.Clear(0xFF)
            logger.info("EPD 2in13 V1 init OK")
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
            logger.warning("EPD not initialized, skipping render_image")
            return

        buf = self._epd.getbuffer(img)
        self._update_count += 1

        needs_full = (
            not self._base_set or self._update_count % self._full_refresh_every == 0
        )

        try:
            if needs_full:
                self._epd.init(self._epd.FULL_UPDATE)
                self._epd.display(buf)
                self._base_set = True
                logger.debug(f"EPD full refresh (update #{self._update_count})")
                time.sleep(2)
            else:
                self._epd.init(self._epd.PART_UPDATE)
                self._epd.display(buf)
                logger.debug(f"EPD partial refresh (update #{self._update_count})")
                time.sleep(0.3)
        except Exception as e:
            logger.error(f"EPD render_image error: {e}", exc_info=True)

    def _push_to_epaper(self) -> None:
        if self._epd is None:
            return
        try:
            buf = self._epd.getbuffer(self._img)
            self._epd.init(self._epd.FULL_UPDATE)
            self._epd.display(buf)
            time.sleep(2)
            self._base_set = True
            self._update_count += 1
        except Exception as e:
            logger.error(f"EPD flush error: {e}", exc_info=True)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self._epd is not None:
            try:
                self._epd.init(self._epd.FULL_UPDATE)
                self._epd.sleep()
                logger.info("EPD sleep OK")
            except Exception as e:
                logger.error(f"EPD sleep error: {e}")
            self._epd = None
