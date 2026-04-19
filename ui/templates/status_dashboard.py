"""Status dashboard screen template."""

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

    y = layout.header(c, title, MARGIN, timestamp)

    for cat in categories:
        if layout.is_overflow(y, c.h):
            y = layout.overflow_marker(c, y)
            break

        cat_name = cat.get("name", "?")
        icon_name = cat.get("icon", "")
        if icon_name and icon_name != "generic":
            icon_key = icon_name
        else:
            icon_key = resolve_icon_key(cat_name, icon_name or "generic")
        icon_img = get_icon(icon_key)
        y = layout.category_row(c, cat_name, icon_img, y)

        for item in cat.get("items", []):
            if layout.is_overflow(y, c.h):
                break
            label = item.get("label", item.get("key", "?"))
            status = item.get("status", "UNKNOWN")
            y = layout.item_row(c, label, status, y)

    status_text = "ok" if timestamp else "no data"
    stale = data.get("stale", False)
    if stale:
        status_text += " | STALE"
    layout.footer(c, status_text)

    return c.to_image()
