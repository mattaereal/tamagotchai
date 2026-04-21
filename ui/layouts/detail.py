"""Single service detail layout -- landscape."""

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

    # Title + status badge on same line
    c.text((MARGIN, 3), name[:20], fill=0)
    icon = {"OK": "[+]", "DEGRADED": "[!]", "DOWN": "[-]", "UNKNOWN": "[?]"}.get(status, "[?]")
    c.right_text(3, icon)
    c.hline(14, fill=0)

    y = 20
    for metric in metrics:
        if y + layout.LINE_H > c.h - layout.FOOTER_RESERVE:
            break
        label = metric.get("label", "")
        value = str(metric.get("value", ""))
        c.text((MARGIN, y), f"{label}:", fill=0)
        c.right_text(y, value[:15])
        y += layout.LINE_H

    if last_check:
        layout.footer(c, f"last: {last_check}")

    return c.to_image()
