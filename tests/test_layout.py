"""Tests for ui.layout primitives."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.canvas import Canvas
from ui import layout, MARGIN


def test_header_returns_y():
    c = Canvas()
    y = layout.header(c, "Test", MARGIN, "12:00:00")
    assert y > MARGIN


def test_header_no_timestamp():
    c = Canvas()
    y = layout.header(c, "Test", MARGIN)
    assert y > MARGIN


def test_divider_returns_y():
    c = Canvas()
    y = 20
    new_y = layout.divider(c, y)
    assert new_y == y + 4


def test_category_row_returns_y():
    c = Canvas()
    y = layout.category_row(c, "Test", None, MARGIN)
    assert y > MARGIN


def test_category_row_with_icon():
    from ui.assets import get_icon

    c = Canvas()
    icon = get_icon("generic")
    y = layout.category_row(c, "Test", icon, MARGIN)
    assert y > MARGIN


def test_item_row_returns_y():
    c = Canvas()
    y = layout.item_row(c, "API", "OK", 20)
    assert y > 20


def test_info_lines_returns_y():
    c = Canvas()
    lines = [("status", "ok"), ("pending", "3")]
    y = layout.info_lines(c, lines, MARGIN)
    assert y > MARGIN


def test_info_lines_overflow():
    c = Canvas()
    lines = [(f"item{i}", str(i)) for i in range(50)]
    y = layout.info_lines(c, lines, MARGIN)
    assert y < c.h


def test_centered_image():
    from PIL import Image

    c = Canvas()
    img = Image.new("1", (90, 90), 255)
    y = layout.centered_image(c, img, 20)
    assert y == 110


def test_footer():
    c = Canvas()
    layout.footer(c, "ok")
    assert True


def test_status_badge():
    c = Canvas()
    y = layout.status_badge(c, "OK", 40)
    assert y > 40


def test_overflow_marker():
    c = Canvas()
    y = layout.overflow_marker(c, 100)
    assert y > 100


def test_is_overflow():
    assert layout.is_overflow(240, 250) is True
    assert layout.is_overflow(200, 250) is False


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
