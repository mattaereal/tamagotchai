"""Font helpers for the e-paper display.

Uses PIL's built-in default bitmap font exclusively.
No TTF dependencies -- proven readable at 122x250 resolution.
"""

from __future__ import annotations

from PIL import ImageFont

_DEFAULT_FONT = ImageFont.load_default()


def get_font(name: str | None = None, size: int | None = None) -> ImageFont.ImageFont:
    """Get a font instance. Currently always returns PIL default.

    The 'name' and 'size' parameters are accepted for forward-compatibility
    but are ignored -- the default bitmap font is always used.
    """
    return _DEFAULT_FONT


def default_font() -> ImageFont.ImageFont:
    return _DEFAULT_FONT


def text_width(text: str, font: ImageFont.ImageFont | None = None) -> int:
    """Return the pixel width of *text* when rendered with *font*."""
    f = font or _DEFAULT_FONT
    bbox = f.getbbox(text)
    return bbox[2] - bbox[0]


def text_height(font: ImageFont.ImageFont | None = None) -> int:
    """Return the pixel height of the font."""
    f = font or _DEFAULT_FONT
    bbox = f.getbbox("Ay")
    return bbox[3] - bbox[1]
