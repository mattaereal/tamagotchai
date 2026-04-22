"""Asset loader for e-paper UI.

Provides icon and sprite loading with proper resizing and
1-bit conversion for the 122x250 monochrome display.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

ICON_SIZE = 12
SPRITE_SIZE = 90

_BUILTIN_ICONS: Dict[str, Image.Image] = {}


def _make_anthropic_icon() -> Image.Image:
    img = Image.new("1", (ICON_SIZE, ICON_SIZE), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (5, 0),
        (6, 0),
        (5, 1),
        (6, 1),
        (4, 3),
        (7, 3),
        (4, 4),
        (7, 4),
        (5, 5),
        (6, 5),
        (2, 4),
        (3, 5),
        (8, 5),
        (9, 4),
        (2, 7),
        (3, 6),
        (8, 6),
        (9, 7),
        (5, 7),
        (6, 7),
        (5, 8),
        (6, 8),
        (5, 10),
        (6, 10),
        (5, 11),
        (6, 11),
        (0, 5),
        (1, 6),
        (10, 6),
        (11, 5),
    ]:
        if 0 <= x < ICON_SIZE and 0 <= y < ICON_SIZE:
            d.point((x, y), fill=0)
    return img


def _make_openai_icon() -> Image.Image:
    img = Image.new("1", (ICON_SIZE, ICON_SIZE), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (3, 0),
        (4, 0),
        (7, 0),
        (8, 0),
        (2, 1),
        (5, 1),
        (6, 1),
        (9, 1),
        (1, 2),
        (4, 2),
        (7, 2),
        (10, 2),
        (0, 3),
        (3, 3),
        (8, 3),
        (11, 3),
        (0, 4),
        (5, 4),
        (6, 4),
        (11, 4),
        (1, 5),
        (4, 5),
        (7, 5),
        (10, 5),
        (1, 6),
        (4, 6),
        (7, 6),
        (10, 6),
        (0, 7),
        (5, 7),
        (6, 7),
        (11, 7),
        (0, 8),
        (3, 8),
        (8, 8),
        (11, 8),
        (1, 9),
        (4, 9),
        (7, 9),
        (10, 9),
        (2, 10),
        (5, 10),
        (6, 10),
        (9, 10),
        (3, 11),
        (4, 11),
        (7, 11),
        (8, 11),
    ]:
        if 0 <= x < ICON_SIZE and 0 <= y < ICON_SIZE:
            d.point((x, y), fill=0)
    return img


def _make_lotus_icon() -> Image.Image:
    img = Image.new("1", (ICON_SIZE, ICON_SIZE), 255)
    d = ImageDraw.Draw(img)
    for x, y in [
        (5, 0),
        (6, 0),
        (4, 1),
        (5, 1),
        (6, 1),
        (7, 1),
        (3, 2),
        (4, 2),
        (7, 2),
        (8, 2),
        (2, 3),
        (3, 3),
        (8, 3),
        (9, 3),
        (1, 4),
        (2, 4),
        (9, 4),
        (10, 4),
        (1, 5),
        (2, 5),
        (5, 5),
        (6, 5),
        (9, 5),
        (10, 5),
        (2, 6),
        (3, 6),
        (5, 6),
        (6, 6),
        (8, 6),
        (9, 6),
        (3, 7),
        (4, 7),
        (7, 7),
        (8, 7),
        (4, 8),
        (5, 8),
        (6, 8),
        (7, 8),
        (3, 9),
        (4, 9),
        (7, 9),
        (8, 9),
        (2, 10),
        (3, 10),
        (8, 10),
        (9, 10),
        (1, 11),
        (2, 11),
        (9, 11),
        (10, 11),
    ]:
        if 0 <= x < ICON_SIZE and 0 <= y < ICON_SIZE:
            d.point((x, y), fill=0)
    return img


def _make_generic_icon() -> Image.Image:
    img = Image.new("1", (ICON_SIZE, ICON_SIZE), 255)
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 9, 9], outline=0, width=1)
    d.point((5, 5), fill=0)
    return img


def _ensure_icons() -> None:
    if _BUILTIN_ICONS:
        return
    _BUILTIN_ICONS["anthropic"] = _make_anthropic_icon()
    _BUILTIN_ICONS["openai"] = _make_openai_icon()
    _BUILTIN_ICONS["lotus"] = _make_lotus_icon()
    _BUILTIN_ICONS["generic"] = _make_generic_icon()
    # Load GitHub icon from file if present
    _github_path = os.path.join(os.path.dirname(__file__), "github_icon.png")
    if os.path.exists(_github_path):
        try:
            _BUILTIN_ICONS["github"] = Image.open(_github_path).convert("1")
        except Exception:
            pass


def get_icon(name: str) -> Optional[Image.Image]:
    _ensure_icons()
    if name in _BUILTIN_ICONS:
        return _BUILTIN_ICONS[name].copy()
    if name.endswith(".png") and os.path.exists(name):
        return load_icon_file(name)
    return _BUILTIN_ICONS.get("generic", _make_generic_icon()).copy()


def load_icon_file(path: str, size: int = ICON_SIZE) -> Optional[Image.Image]:
    try:
        img = Image.open(path).convert("L")
        resized = img.resize((size, size), Image.LANCZOS)
        return resized.convert("1", dither=Image.FLOYDSTEINBERG)
    except Exception as e:
        logger.warning(f"Failed to load icon {path}: {e}")
        return None


def resolve_icon_key(category_name: str, fallback: str = "generic") -> str:
    name_lower = category_name.lower()
    if "claude" in name_lower or "anthropic" in name_lower:
        return "anthropic"
    if "openai" in name_lower or "gpt" in name_lower:
        return "openai"
    if "github" in name_lower:
        return "github"
    if "lotus" in name_lower:
        return "lotus"
    return fallback


def load_sprite(path: str, size: int = SPRITE_SIZE) -> Optional[Image.Image]:
    if not path or not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("L")
        resized = img.resize((size, size), Image.LANCZOS)
        return resized.convert("1", dither=Image.FLOYDSTEINBERG)
    except Exception as e:
        logger.warning(f"Failed to load sprite {path}: {e}")
        return None


def load_opencode_logo(size: int = 48) -> Optional[Image.Image]:
    """Load the OpenCode logo, converting to 1-bit e-paper format.

    The source logo is a 28x28 pixel-art PNG. We scale it with
    NEAREST to preserve crisp edges on the low-res e-paper panel.
    """
    path = os.path.join(os.path.dirname(__file__), "opencode_logo.png")
    if not os.path.exists(path):
        logger.warning(f"OpenCode logo not found: {path}")
        return None
    try:
        img = Image.open(path)
        # Convert palette/RGBA to grayscale, then 1-bit
        gray = img.convert("L")
        resized = gray.resize((size, size), Image.NEAREST)
        return resized.convert("1", dither=Image.NONE)
    except Exception as e:
        logger.warning(f"Failed to load OpenCode logo: {e}")
        return None


def builtin_icon_names() -> list[str]:
    _ensure_icons()
    return list(_BUILTIN_ICONS.keys())
