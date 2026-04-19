"""Waveshare 2.13" V3 e-paper display backend.

Portrait mode: images created at (122, 250) matching EPD native dims.
getbuffer() passes through directly when image dims match EPD dims.
Partial refresh: displayPartBaseImage() for full, displayPartial() for fast updates.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Union

from PIL import Image, ImageDraw

from ..display.base import DisplayBackend
from ..config import DisplayConfig

logger = logging.getLogger(__name__)

try:
    from waveshare_epd import epd2in13_V3  # type: ignore
except Exception:
    epd2in13_V3 = None

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


class Waveshare2in13V3Display(DisplayBackend):
    """Waveshare 2.13" V3 b/w e-paper display backend (portrait mode)."""

    def __init__(self, config: Union[DisplayConfig, Dict[str, Any]]):
        self._epd = None
        self._update_count = 0
        self._base_set = False
        self._full_refresh_every = _get_display_value(
            config, "full_refresh_every_n_updates", 50
        )
        self._init_display()
        self._width = self._epd.width  # 122
        self._height = self._epd.height  # 250
        self._img: Image.Image = Image.new("1", (self._width, self._height), 255)
        self._draw = ImageDraw.Draw(self._img)
        logger.info(
            f"Waveshare2in13V3 initialized: portrait {self._width}x{self._height}"
        )

    def _init_display(self) -> None:
        if epd2in13_V3 is None:
            raise RuntimeError(
                "waveshare_epd.epd2in13_V3 not available. "
                "Install: sudo apt install python3-lgpio python3-spidev && "
                "git clone https://github.com/waveshareteam/e-Paper && "
                "cd e-Paper/RaspberryPi_JetsonNano/python && "
                "sudo python3 setup.py install"
            )
        try:
            self._epd = epd2in13_V3.EPD()
            self._epd.init()
            self._epd.Clear(0xFF)
            logger.info("EPD 2in13 V3 init OK")
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

        self._push_to_epaper()

    def render_image(self, img: Image.Image) -> None:
        """Render a PIL Image directly to the EPD.

        Uses displayPartial() for fast updates by default.
        Only uses displayPartBaseImage() on first render or
        periodic ghosting cleanup (every N updates).

        Args:
            img: PIL Image in mode '1', sized (width, height) = (122, 250).
        """
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
                self._epd.displayPartBaseImage(buf)
                self._base_set = True
                logger.debug(f"EPD full refresh (update #{self._update_count})")
                time.sleep(2)
            else:
                self._epd.displayPartial(buf)
                logger.debug(f"EPD partial refresh (update #{self._update_count})")
                time.sleep(0.3)
        except Exception as e:
            logger.error(f"EPD render_image error: {e}", exc_info=True)

    def _push_to_epaper(self) -> None:
        if self._epd is None:
            logger.warning("EPD not initialized, skipping flush")
            return
        try:
            buf = self._epd.getbuffer(self._img)
            self._epd.displayPartBaseImage(buf)
            self._base_set = True
            self._update_count += 1
            logger.debug(f"EPD frame flushed (update #{self._update_count})")
        except Exception as e:
            logger.error(f"EPD flush error: {e}", exc_info=True)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        """Put EPD to sleep. Only call on shutdown."""
        if self._epd is not None:
            try:
                self._epd.sleep()
                logger.info("EPD sleep OK")
            except Exception as e:
                logger.error(f"EPD sleep error: {e}")
            self._epd = None
