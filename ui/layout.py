"""Layout primitives for the 122x250 e-paper display.

Every function takes (canvas, y) and returns the new y position.
This keeps layout composable and testable without magic numbers.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

from .canvas import Canvas
from . import MARGIN

LINE_H: int = 12
LINE_H_SMALL: int = 11
ICON_SIZE: int = 12
ITEM_INDENT: int = 8
TEXT_INDENT: int = 28
MAX_LABEL: int = 14
FOOTER_RESERVE: int = 14

_STATUS_ICONS = {
    "OK": "[+]",
    "DEGRADED": "[!]",
    "DOWN": "[-]",
    "UNKNOWN": "[?]",
}


def header(c: Canvas, title: str, y: int, timestamp: str = "") -> int:
    c.text((MARGIN, y), title, fill=0)
    y += LINE_H + 2
    if timestamp:
        c.text((MARGIN, y), timestamp, fill=0)
        y += LINE_H + 2
    y = divider(c, y)
    return y


def divider(c: Canvas, y: int) -> int:
    c.hline(y, fill=0)
    return y + 4


def category_row(c: Canvas, name: str, icon_img: Optional[Image.Image], y: int) -> int:
    if icon_img:
        c.paste(icon_img, (MARGIN, y))
        c.text((MARGIN + 16, y), name, fill=0)
    else:
        c.text((MARGIN, y), name, fill=0)
    return y + LINE_H


def item_row(
    c: Canvas, label: str, status: str, y: int, indent: int = ITEM_INDENT
) -> int:
    cicon = _STATUS_ICONS.get(status, "[?]")
    display_label = c.truncate(label, MAX_LABEL)
    c.text((MARGIN + indent, y), cicon, fill=0)
    c.text((MARGIN + TEXT_INDENT, y), display_label, fill=0)
    return y + LINE_H


def info_lines(
    c: Canvas,
    lines: list[tuple[str, str]],
    y: int,
    max_y: Optional[int] = None,
    line_h: int = LINE_H_SMALL,
) -> int:
    if max_y is None:
        max_y = c.h - FOOTER_RESERVE
    for label, value in lines:
        if y + line_h > max_y:
            break
        if label:
            text = f"{label}: {value}"
        else:
            text = value
        c.text((MARGIN, y), text, fill=0)
        y += line_h
    return y


def centered_image(c: Canvas, img: Image.Image, y: int) -> int:
    x = (c.w - img.width) // 2
    c.paste(img, (x, y))
    return y + img.height


def footer(c: Canvas, text: str) -> None:
    y = c.h - LINE_H - 2
    c.text((MARGIN, y), text, fill=0)


def status_badge(c: Canvas, status: str, y: int) -> int:
    label = _STATUS_ICONS.get(status, "[?]")
    cx = c.w // 2
    c.filled_rect((cx - 20, y, cx + 20, y + 16), fill=0)
    c.text((cx - 14, y + 3), label, fill=255)
    return y + 20


def overflow_marker(c: Canvas, y: int) -> int:
    c.text((MARGIN, y), "...", fill=0)
    return y + LINE_H


def is_overflow(y: int, height: int, reserve: int = FOOTER_RESERVE) -> bool:
    return y + LINE_H > height - reserve
