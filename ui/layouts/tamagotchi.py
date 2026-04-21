"""Tamagotchi layout -- landscape profile-card style.

Split-panel design:
  - Left: framed sprite (70x70) + name below
  - Right: info lines stacked vertically
  - Footer: mood + timestamp

Used by core/screens/tamagotchi.py.
"""

from __future__ import annotations

from datetime import datetime

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from ..assets import load_sprite
from . import register

_SPRITE_SIZE = 70
_LEFT_COL_W = 78
_RIGHT_COL_X = _LEFT_COL_W + 4
_LINE_H = 11


@register("tamagotchi")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "")
    mood = data.get("mood", "idle")
    frame = data.get("frame", 0)
    sprites = data.get("sprites", {})
    info_lines = data.get("info_lines", [])
    fetch_error = data.get("fetch_error", False)
    last_checked = data.get("last_checked", "")

    # Left column: framed sprite
    sprite_y = 12
    sprite = sprites.get(mood)
    if not sprite:
        available = list(sprites.values())
        if available:
            sprite = available[frame % len(available)]

    box_x = MARGIN + 4
    box_y = sprite_y
    c.rect((box_x, box_y, box_x + _SPRITE_SIZE, box_y + _SPRITE_SIZE), outline=0)
    c.rect((box_x + 2, box_y + 2, box_x + _SPRITE_SIZE - 2, box_y + _SPRITE_SIZE - 2), outline=0)

    if sprite:
        # Scale sprite to fit in 70x70 box
        if sprite.width != _SPRITE_SIZE or sprite.height != _SPRITE_SIZE:
            sprite = sprite.resize((_SPRITE_SIZE, _SPRITE_SIZE), Image.NEAREST)
        c.paste(sprite, (box_x, box_y))
    else:
        _draw_fallback_face(c, mood, box_x, box_y, _SPRITE_SIZE)

    # Name below sprite
    name_y = box_y + _SPRITE_SIZE + 6
    if name:
        c.centered_text(name_y, name[:12], fill=0)

    # Right column: info lines
    y = 14
    max_y = c.h - layout.FOOTER_RESERVE - 2

    if fetch_error:
        c.text((_RIGHT_COL_X, y), "[-] connection error", fill=0)
    else:
        for line in info_lines:
            if y + _LINE_H > max_y:
                break
            label = line.get("label", "")
            value = line.get("value", "")
            text = f"{label}: {value}" if label else value
            text = c.truncate(text, 30)
            c.text((_RIGHT_COL_X, y), text, fill=0)
            y += _LINE_H

    # Footer: mood + timestamp
    footer_y = c.h - layout.LINE_H - 2
    if last_checked:
        try:
            dt = datetime.fromisoformat(last_checked)
            ts = dt.strftime("%H:%M:%S")
            c.text((MARGIN, footer_y), f"{mood} | {ts}", fill=0)
        except (ValueError, TypeError):
            c.text((MARGIN, footer_y), f"mood: {mood}", fill=0)
    else:
        c.text((MARGIN, footer_y), f"mood: {mood}", fill=0)

    return c.to_image()


def _draw_fallback_face(c: Canvas, mood: str, x: int, y: int, size: int) -> None:
    """Draw a simple fallback face inside the given box."""
    cx = x + size // 2
    cy = y + size // 2
    face_r = size // 3
    eye_y = cy - size // 10
    left_eye_x = cx - size // 8
    right_eye_x = cx + size // 8

    c.ellipse([cx - face_r, cy - face_r, cx + face_r, cy + face_r], outline=0, width=1)
    c.ellipse([left_eye_x - 3, eye_y - 3, left_eye_x + 3, eye_y + 3], fill=0)
    c.ellipse([right_eye_x - 3, eye_y - 3, right_eye_x + 3, eye_y + 3], fill=0)

    mouth_y = cy + size // 8
    if mood == "idle":
        c.arc(
            [cx - 8, mouth_y - 4, cx + 8, mouth_y + 6],
            start=0,
            end=180,
            fill=0,
            width=1,
        )
    elif mood == "working":
        c.line([(cx - 6, mouth_y), (cx + 6, mouth_y)], fill=0, width=1)
    else:
        c.arc(
            [cx - 8, mouth_y, cx + 8, mouth_y + 10], start=180, end=360, fill=0, width=1
        )
