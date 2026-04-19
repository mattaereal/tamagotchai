"""Boot screen template."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("boot")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Lotus Companion")
    version = data.get("version", "1.0")

    c.rect((MARGIN, MARGIN, c.w - MARGIN, c.h - MARGIN), outline=0)
    c.rect((MARGIN + 2, MARGIN + 2, c.w - MARGIN - 2, c.h - MARGIN - 2), outline=0)

    c.centered_text(60, name, fill=0)
    c.centered_text(78, f"v{version}", fill=0)

    c.hline(100, fill=0)
    c.centered_text(110, "Starting...", fill=0)

    return c.to_image()
