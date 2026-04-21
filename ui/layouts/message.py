"""Message / alert layout -- landscape."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("message")
def render(c: Canvas, data: dict) -> Image.Image:
    title = data.get("title", "")
    body = data.get("body", [])
    hint = data.get("hint", "")

    if isinstance(body, str):
        body = [body]

    y = MARGIN + 4

    if title:
        c.text((MARGIN, y), title[:20], fill=0)
        c.hline(y + 12, fill=0)
        y += 18

    for line in body:
        if y + layout.LINE_H > c.h - layout.FOOTER_RESERVE:
            break
        text = str(line)
        # Wrap text to fit width
        if len(text) > 40:
            text = text[:37] + "..."
        c.text((MARGIN, y), text, fill=0)
        y += layout.LINE_H

    if hint:
        layout.footer(c, hint)

    return c.to_image()
