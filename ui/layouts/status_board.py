"""Status board layout -- landscape compact rows.

Categories render as horizontal bands:
  - Category header with icon
  - Items as compact horizontal status chips

Overflow: +N indicator when categories don't fit.

Used by core/screens/status_board.py.
"""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from ..assets import get_icon
from . import register

_STATUS_ICONS = {
    "OK": "[+]",
    "DEGRADED": "[!]",
    "DOWN": "[-]",
    "UNKNOWN": "[?]",
}

_LINE_H = 11
_HEADER_H = 13


@register("status_board")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Status")
    timestamp = data.get("timestamp", "")
    categories = data.get("categories", [])
    footer_text = data.get("footer_text", "no data")

    # Title bar
    c.text((MARGIN, 3), name, fill=0)
    if timestamp:
        c.right_text(3, timestamp)
    c.hline(14, fill=0)

    y = 18
    max_y = c.h - layout.FOOTER_RESERVE - 2
    shown = 0

    for cat in categories:
        cat_h = _HEADER_H + _LINE_H + 2  # header + items row + gap
        if y + cat_h > max_y:
            break

        icon_key = cat.get("icon", "generic")
        icon_img = get_icon(icon_key)
        cat_name = cat.get("name", "")

        # Category header with icon
        if icon_img:
            c.paste(icon_img, (MARGIN, y))
            c.text((MARGIN + 16, y), cat_name[:12], fill=0)
        else:
            c.text((MARGIN, y), cat_name[:14], fill=0)
        y += _HEADER_H

        # Items as compact horizontal chips
        items = cat.get("items", [])
        x = MARGIN
        chip_w = 38  # approximate width per chip
        chips_in_row = (c.w - 2 * MARGIN) // chip_w

        for i, item in enumerate(items):
            if i >= chips_in_row:
                # More items than fit - add ellipsis
                c.text((x, y), "...", fill=0)
                break
            label = item.get("label", "?")
            status = item.get("status", "UNKNOWN")
            icon = _STATUS_ICONS.get(status, "[?]")
            chip = f"{label}{icon}"
            # Truncate label if needed
            if len(chip) > 10:
                chip = label[:6] + ".." + icon
            c.text((x, y), chip, fill=0)
            x += chip_w

        y += _LINE_H + 2
        shown += 1

    # +N more indicator
    if shown < len(categories):
        remaining = len(categories) - shown
        c.text((MARGIN, y), f"+{remaining} more", fill=0)

    layout.footer(c, footer_text)
    return c.to_image()
