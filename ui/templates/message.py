"""Message / alert screen template."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("message")
def render(c: Canvas, data: dict) -> Image.Image:
    title = data.get("title", "")
    body = data.get("body", data.get("message", "No message"))
    hint = data.get("hint", "")

    y = MARGIN + 4

    if title:
        c.filled_rect((MARGIN, y, c.w - MARGIN, y + 16), fill=0)
        c.centered_text(y + 3, title, fill=255)
        y += 24
        c.hline(y, fill=0)
        y += 8

    if isinstance(body, str):
        body = [body]

    for line in body:
        if y + layout.LINE_H > c.content_bottom:
            c.text((MARGIN, y), "...", fill=0)
            break
        c.text((MARGIN, y), line, fill=0)
        y += layout.LINE_H

    if hint:
        layout.footer(c, hint)

    return c.to_image()
