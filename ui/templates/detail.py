"""Single service detail screen template."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register


@register("detail")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Service")
    status = data.get("status", "UNKNOWN")
    metrics = data.get("metrics", [])
    last_check = data.get("last_check", "")

    y = layout.header(c, name, MARGIN)

    y = layout.status_badge(c, status, y)
    y += 4
    c.hline(y, fill=0)
    y += 6

    for metric in metrics:
        if layout.is_overflow(y, c.h):
            y = layout.overflow_marker(c, y)
            break
        label = metric.get("label", "")
        value = str(metric.get("value", ""))
        c.text((MARGIN, y), f"{label}:", fill=0)
        c.right_text(y, value, fill=0)
        y += layout.LINE_H

    if last_check:
        layout.footer(c, f"last: {last_check}")

    return c.to_image()
