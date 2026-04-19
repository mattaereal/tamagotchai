"""WiFi setup / provisioning screen template."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("setup")
def render(c: Canvas, data: dict) -> Image.Image:
    ssid = data.get("ssid", "AI-BOARD-SETUP")
    url = data.get("url", "http://10.42.0.1")

    c.filled_rect((MARGIN, MARGIN, c.w - MARGIN, MARGIN + 16), fill=0)
    c.centered_text(MARGIN + 3, "SETUP MODE", fill=255)

    y = MARGIN + 24
    c.hline(y, fill=0)
    y += 8

    c.centered_text(y, "Connect to:", fill=0)
    y += 16

    c.filled_rect((8, y, c.w - 8, y + 16), fill=0)
    c.centered_text(y + 3, ssid, fill=255)
    y += 24

    c.centered_text(y, "Then open:", fill=0)
    y += 16

    c.filled_rect((8, y, c.w - 8, y + 16), fill=0)
    c.centered_text(y + 3, url, fill=255)
    y += 28

    c.hline(y, fill=0)
    y += 8
    c.centered_text(y, "On your phone", fill=0)

    return c.to_image()
