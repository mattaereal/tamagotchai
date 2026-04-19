"""Error / offline screen template."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("error")
def render(c: Canvas, data: dict) -> Image.Image:
    message = data.get("message", "Connection lost")
    detail = data.get("detail", "")
    last_ok = data.get("last_ok", "")

    cx = c.w // 2

    c.line([(cx - 16, 40), (cx + 16, 72)], fill=0, width=2)
    c.line([(cx + 16, 40), (cx - 16, 72)], fill=0, width=2)

    c.centered_text(82, "ERROR", fill=0)

    y = 100
    c.hline(y, fill=0)
    y += 8

    c.centered_text(y, message, fill=0)
    y += layout.LINE_H + 4

    if detail:
        words = detail.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if len(test) > 18:
                if y + layout.LINE_H > c.h - layout.FOOTER_RESERVE:
                    break
                c.centered_text(y, line, fill=0)
                y += layout.LINE_H
                line = word
            else:
                line = test
        if line and y + layout.LINE_H <= c.h - layout.FOOTER_RESERVE:
            c.centered_text(y, line, fill=0)

    if last_ok:
        layout.footer(c, f"last ok: {last_ok}")

    return c.to_image()
