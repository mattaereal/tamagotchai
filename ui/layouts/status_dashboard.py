"""Status dashboard layout -- landscape."""

from __future__ import annotations

from typing import Dict, Optional

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from ..assets import get_icon, resolve_icon_key
from . import register


@register("status_dashboard")
def render(c: Canvas, data: dict) -> Image.Image:
    title = data.get("name", "AI Status")
    timestamp = data.get("timestamp", "")
    categories = data.get("categories", [])

    # Title bar
    c.text((MARGIN, 3), title, fill=0)
    if timestamp:
        c.right_text(3, timestamp)
    c.hline(14, fill=0)

    y = 18
    for cat in categories:
        if y + layout.LINE_H * 2 > c.h - layout.FOOTER_RESERVE:
            break

        cat_name = cat.get("name", "?")
        icon_name = cat.get("icon", "")
        if icon_name and icon_name != "generic":
            icon_key = icon_name
        else:
            icon_key = resolve_icon_key(cat_name, icon_name or "generic")
        icon_img = get_icon(icon_key)

        # Category header
        if icon_img:
            c.paste(icon_img, (MARGIN, y))
            c.text((MARGIN + 16, y), cat_name[:10], fill=0)
        else:
            c.text((MARGIN, y), cat_name[:12], fill=0)
        y += layout.LINE_H + 2

        # Items as horizontal chips
        x = MARGIN
        chip_w = 40
        for item in cat.get("items", []):
            if x + chip_w > c.w - MARGIN:
                break
            label = item.get("label", item.get("key", "?"))
            status = item.get("status", "UNKNOWN")
            icon = {"OK": "[+]", "DEGRADED": "[!]", "DOWN": "[-]", "UNKNOWN": "[?]"}.get(status, "[?]")
            chip = f"{label}{icon}"
            if len(chip) > 9:
                chip = label[:5] + ".." + icon
            c.text((x, y), chip, fill=0)
            x += chip_w
        y += layout.LINE_H + 4

    status_text = "ok" if timestamp else "no data"
    stale = data.get("stale", False)
    if stale:
        status_text += " | STALE"
    layout.footer(c, status_text)

    return c.to_image()
