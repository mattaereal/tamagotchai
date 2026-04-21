"""WiFi setup / provisioning layout -- landscape."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("setup")
def render(c: Canvas, data: dict) -> Image.Image:
    ssid = data.get("ssid", "AI-BOARD-SETUP")
    url = data.get("url", "http://10.42.0.1")

    # Title bar
    c.filled_rect((MARGIN, MARGIN, c.w - MARGIN, MARGIN + 14), fill=0)
    c.centered_text(MARGIN + 2, "SETUP MODE", fill=255)
    c.hline(22, fill=0)

    # Left: instructions
    y = 30
    c.text((MARGIN, y), "Connect to:", fill=0)
    y += 12
    c.filled_rect((MARGIN, y, MARGIN + 100, y + 14), fill=0)
    c.text((MARGIN + 4, y + 2), ssid[:16], fill=255)
    y += 22

    c.text((MARGIN, y), "Then open:", fill=0)
    y += 12
    c.filled_rect((MARGIN, y, MARGIN + 120, y + 14), fill=0)
    c.text((MARGIN + 4, y + 2), url[:20], fill=255)

    # Right: hint
    hint_x = 140
    hint_y = 32
    c.text((hint_x, hint_y), "On your phone:", fill=0)
    hint_y += 12
    c.text((hint_x, hint_y), "1. Open WiFi settings", fill=0)
    hint_y += 11
    c.text((hint_x, hint_y), "2. Select the network", fill=0)
    hint_y += 11
    c.text((hint_x, hint_y), "3. Open browser URL", fill=0)

    return c.to_image()
