"""Tests for ui.canvas, ui.layout, and ui.fonts modules."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from ui.canvas import Canvas
from ui import layout, MARGIN


# --- Canvas ---


def test_canvas_dimensions():
    c = Canvas()
    assert c.w == 122
    assert c.h == 250
    img = c.to_image()
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_canvas_custom_size():
    c = Canvas(100, 200)
    assert c.w == 100
    assert c.h == 200


def test_canvas_content_bounds():
    c = Canvas()
    assert c.content_left == 4
    assert c.content_right == 118
    assert c.content_width == 114


def test_canvas_text():
    c = Canvas()
    c.text((4, 4), "Hello", fill=0)
    img = c.to_image()
    assert img.mode == "1"


def test_canvas_centered_text():
    c = Canvas()
    c.centered_text(50, "Center", fill=0)


def test_canvas_right_text():
    c = Canvas()
    c.right_text(50, "Right", fill=0)


def test_canvas_hline():
    c = Canvas()
    c.hline(30, fill=0)


def test_canvas_rect():
    c = Canvas()
    c.rect((4, 4, 50, 50), outline=0)


def test_canvas_filled_rect():
    c = Canvas()
    c.filled_rect((4, 4, 50, 50), fill=0)


def test_canvas_ellipse():
    c = Canvas()
    c.ellipse((4, 4, 50, 50), outline=0)


def test_canvas_arc():
    c = Canvas()
    c.arc((4, 4, 50, 50), start=0, end=180, fill=0)


def test_canvas_line():
    c = Canvas()
    c.line([(4, 4), (50, 50)], fill=0)


def test_canvas_point():
    c = Canvas()
    c.point((10, 10), fill=0)


def test_canvas_truncate():
    c = Canvas()
    assert c.truncate("Hello", 10) == "Hello"
    assert c.truncate("Hello World", 8) == "Hello..."


def test_canvas_paste():
    c = Canvas()
    icon = Image.new("1", (12, 12), 255)
    c.paste(icon, (4, 4))


def test_canvas_to_image_copy():
    c = Canvas()
    c.text((4, 4), "test", fill=0)
    img1 = c.to_image()
    c.text((4, 20), "more", fill=0)
    img2 = c.to_image()
    assert img1 != img2


# --- Fonts ---


def test_default_font():
    from ui.fonts import get_font, default_font

    f = get_font()
    assert f is not None
    assert f is default_font()


def test_text_width():
    from ui.fonts import text_width

    w = text_width("Hello")
    assert w > 0


def test_text_height():
    from ui.fonts import text_height

    h = text_height()
    assert h > 0


# --- Layout ---


def test_layout_header():
    c = Canvas()
    y = layout.header(c, "Title", MARGIN, "12:00:00")
    assert y > MARGIN


def test_layout_header_no_timestamp():
    c = Canvas()
    y = layout.header(c, "Title", MARGIN)
    assert y > MARGIN


def test_layout_divider():
    c = Canvas()
    y = layout.divider(c, 20)
    assert y == 24


def test_layout_category_row_with_icon():
    c = Canvas()
    icon = Image.new("1", (12, 12), 255)
    y = layout.category_row(c, "Test", icon, 10)
    assert y == 22


def test_layout_category_row_no_icon():
    c = Canvas()
    y = layout.category_row(c, "Test", None, 10)
    assert y == 22


def test_layout_item_row():
    c = Canvas()
    y = layout.item_row(c, "API", "OK", 10)
    assert y == 22


def test_layout_info_lines():
    c = Canvas()
    lines = [("label", "value"), ("", "plain")]
    y = layout.info_lines(c, lines, 10)
    assert y > 10


def test_layout_info_lines_overflow():
    c = Canvas()
    lines = [("l", str(i)) for i in range(50)]
    y = layout.info_lines(c, lines, 10)
    assert y < c.h


def test_layout_centered_image():
    c = Canvas()
    img = Image.new("1", (40, 40), 255)
    y = layout.centered_image(c, img, 10)
    assert y == 50


def test_layout_footer():
    c = Canvas()
    layout.footer(c, "ok")


def test_layout_status_badge():
    c = Canvas()
    y = layout.status_badge(c, "OK", 10)
    assert y == 30


def test_layout_overflow_marker():
    c = Canvas()
    y = layout.overflow_marker(c, 10)
    assert y == 22


def test_layout_is_overflow():
    c = Canvas()
    assert not layout.is_overflow(10, c.h)
    assert layout.is_overflow(c.h - 10, c.h)


# --- Assets ---


def test_builtin_icons():
    from ui.assets import get_icon, builtin_icon_names

    names = builtin_icon_names()
    assert "anthropic" in names
    assert "openai" in names
    assert "lotus" in names
    assert "generic" in names


def test_get_icon_returns_image():
    from ui.assets import get_icon

    icon = get_icon("anthropic")
    assert icon is not None
    assert icon.size == (12, 12)
    assert icon.mode == "1"


def test_get_icon_unknown_returns_generic():
    from ui.assets import get_icon

    icon = get_icon("nonexistent")
    assert icon is not None
    assert icon.size == (12, 12)


def test_resolve_icon_key():
    from ui.assets import resolve_icon_key

    assert resolve_icon_key("Claude API") == "anthropic"
    assert resolve_icon_key("OpenAI GPT") == "openai"
    assert resolve_icon_key("Lotus Health") == "lotus"
    assert resolve_icon_key("Custom Service") == "generic"


def test_load_sprite_missing():
    from ui.assets import load_sprite

    assert load_sprite("/nonexistent/path.png") is None


def test_load_sprite_none():
    from ui.assets import load_sprite

    assert load_sprite("") is None
    assert load_sprite(None) is None


def test_load_icon_file():
    import tempfile

    from ui.assets import load_icon_file

    with tempfile.TemporaryDirectory() as td:
        img = Image.new("RGB", (24, 24), (0, 0, 0))
        path = os.path.join(td, "icon.png")
        img.save(path)
        result = load_icon_file(path)
        assert result is not None
        assert result.size == (12, 12)
        assert result.mode == "1"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
