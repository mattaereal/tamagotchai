"""Boot screen layout -- landscape."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import MARGIN
from . import register


@register("boot")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Lotus Companion")
    version = data.get("version", "1.0")

    # Double border frame
    c.rect((MARGIN, MARGIN, c.w - MARGIN, c.h - MARGIN), outline=0)
    c.rect((MARGIN + 2, MARGIN + 2, c.w - MARGIN - 2, c.h - MARGIN - 2), outline=0)

    # Centered text in landscape
    c.centered_text(c.h // 2 - 10, name, fill=0)
    c.centered_text(c.h // 2 + 8, f"v{version}", fill=0)

    c.hline(c.h // 2 + 22, fill=0)
    c.centered_text(c.h // 2 + 28, "Starting...", fill=0)

    return c.to_image()
