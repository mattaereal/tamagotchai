"""Idle / mascot layout -- landscape."""

from __future__ import annotations

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register

_SPRITE_SIZE = 70


@register("idle")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "")
    mood = data.get("mood", "idle")
    sprite = data.get("sprite")
    info = data.get("info", [])

    # Left: sprite or fallback face
    sprite_x = MARGIN + 4
    sprite_y = (c.h - _SPRITE_SIZE) // 2

    if sprite and isinstance(sprite, Image.Image):
        if sprite.width != _SPRITE_SIZE or sprite.height != _SPRITE_SIZE:
            sprite = sprite.resize((_SPRITE_SIZE, _SPRITE_SIZE), Image.NEAREST)
        c.paste(sprite, (sprite_x, sprite_y))
    else:
        _draw_fallback_face(c, mood, sprite_x, sprite_y)

    # Name below sprite
    if name:
        c.centered_text(sprite_y + _SPRITE_SIZE + 4, name[:12], fill=0)

    # Right: info lines
    right_x = sprite_x + _SPRITE_SIZE + 10
    y = (c.h - len(info) * layout.LINE_H_SMALL) // 2
    for line in info:
        if isinstance(line, dict):
            label = line.get("label", "")
            value = str(line.get("value", ""))
            text = f"{label}: {value}" if label else value
        else:
            text = str(line)
        c.text((right_x, y), text, fill=0)
        y += layout.LINE_H_SMALL

    if mood:
        layout.footer(c, mood)

    return c.to_image()


def _draw_fallback_face(c: Canvas, mood: str, x: int, y: int) -> None:
    cx = x + _SPRITE_SIZE // 2
    cy = y + _SPRITE_SIZE // 2
    face_r = _SPRITE_SIZE // 3
    eye_y = cy - 6
    left_eye_x = cx - 8
    right_eye_x = cx + 8

    c.ellipse([cx - face_r, cy - face_r, cx + face_r, cy + face_r], outline=0, width=1)
    c.ellipse([left_eye_x - 3, eye_y - 3, left_eye_x + 3, eye_y + 3], fill=0)
    c.ellipse([right_eye_x - 3, eye_y - 3, right_eye_x + 3, eye_y + 3], fill=0)

    mouth_y = cy + 8
    if mood == "idle":
        c.arc(
            [cx - 6, mouth_y - 3, cx + 6, mouth_y + 4],
            start=0, end=180, fill=0, width=1,
        )
    elif mood == "working":
        c.line([(cx - 4, mouth_y), (cx + 4, mouth_y)], fill=0, width=1)
    else:
        c.arc(
            [cx - 6, mouth_y, cx + 6, mouth_y + 6], start=180, end=360, fill=0, width=1
        )
