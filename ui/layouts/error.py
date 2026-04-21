"""Error / offline layout -- landscape."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("error")
def render(c: Canvas, data: dict) -> Image.Image:
    message = data.get("message", "Error")
    detail = data.get("detail", "")
    last_ok = data.get("last_ok", "")

    # Large error icon left
    c.text((MARGIN, c.h // 2 - 10), "[-]", fill=0)

    # Message right of icon
    msg_x = MARGIN + 30
    y = c.h // 2 - 10
    c.text((msg_x, y), message[:25], fill=0)
    y += layout.LINE_H

    if detail:
        # Wrap detail to fit remaining width
        words = str(detail).split()
        line = ""
        for word in words:
            if len(line) + len(word) + 1 > 30:
                c.text((msg_x, y), line, fill=0)
                y += layout.LINE_H_SMALL
                line = word
            else:
                line = (line + " " + word) if line else word
        if line:
            c.text((msg_x, y), line, fill=0)
            y += layout.LINE_H_SMALL

    if last_ok:
        c.text((msg_x, y + 4), f"last ok: {last_ok}", fill=0)

    return c.to_image()
