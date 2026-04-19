"""Idle / mascot / decorative screen template."""

from __future__ import annotations

from typing import Optional

from PIL import Image, ImageDraw

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register

_SPRITE_SIZE = 90


@register("idle")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "")
    mood = data.get("mood", "idle")
    sprite = data.get("sprite")
    info = data.get("info", [])

    y = MARGIN + 14

    if sprite and isinstance(sprite, Image.Image):
        y = layout.centered_image(c, sprite, y)
    else:
        _draw_fallback_face(c, mood, y)
        y += _SPRITE_SIZE

    y += 6

    if name:
        c.centered_text(y, name, fill=0)
        y += layout.LINE_H + 2

    c.hline(y, fill=0)
    y += 4

    for line in info:
        if isinstance(line, dict):
            label = line.get("label", "")
            value = str(line.get("value", ""))
            text = f"{label}: {value}" if label else value
        else:
            text = str(line)
        if y + layout.LINE_H_SMALL > c.h - layout.FOOTER_RESERVE:
            break
        c.text((MARGIN, y), text, fill=0)
        y += layout.LINE_H_SMALL

    if mood:
        layout.footer(c, mood)

    return c.to_image()


def _draw_fallback_face(c: Canvas, mood: str, top_y: int) -> None:
    cx = c.w // 2
    cy = top_y + _SPRITE_SIZE // 2
    face_r = 28
    eye_y = cy - 8
    left_eye_x = cx - 10
    right_eye_x = cx + 10

    c.ellipse([cx - face_r, cy - face_r, cx + face_r, cy + face_r], outline=0, width=1)

    c.ellipse([left_eye_x - 3, eye_y - 3, left_eye_x + 3, eye_y + 3], fill=0)
    c.ellipse([right_eye_x - 3, eye_y - 3, right_eye_x + 3, eye_y + 3], fill=0)

    mouth_y = cy + 10
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
