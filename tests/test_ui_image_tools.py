"""Tests for ui.image_tools: presets, prepare pipeline, dithering."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image


# --- Presets ---


def test_presets():
    from ui.image_tools.presets import get_preset, PRESETS

    assert "photo" in PRESETS
    assert "logo" in PRESETS
    assert "portrait" in PRESETS
    assert "mascot" in PRESETS
    p = get_preset("photo")
    assert p.width == 122
    assert p.height == 250


def test_preset_unknown_raises():
    from ui.image_tools.presets import get_preset

    try:
        get_preset("nonexistent")
        assert False
    except KeyError:
        pass


# --- Prepare Pipeline ---


def test_prepare_image():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        img = Image.new("RGB", (200, 400), (128, 128, 128))
        img.save(inp)
        result = prepare_image(inp, out, mode="photo")
        assert os.path.exists(out)
        assert result.output_image.mode == "1"
        assert result.output_image.size == (122, 250)


def test_prepare_image_portrait():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        img = Image.new("RGB", (200, 200), (64, 64, 64))
        img.save(inp)
        result = prepare_image(inp, out, mode="portrait")
        assert result.output_image.size == (90, 90)


def test_prepare_image_with_preview():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        prev = os.path.join(td, "stages")
        img = Image.new("RGB", (200, 400), (128, 128, 128))
        img.save(inp)
        result = prepare_image(inp, out, mode="photo", preview_dir=prev)
        assert os.path.exists(os.path.join(prev, "1_grayscale.png"))
        assert os.path.exists(os.path.join(prev, "2_contrast.png"))
        assert os.path.exists(os.path.join(prev, "4_dithered.png"))


def test_prepare_image_threshold():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        img = Image.new("RGB", (200, 400), (200, 200, 200))
        img.save(inp)
        result = prepare_image(inp, out, mode="logo")
        assert result.output_image.mode == "1"


def test_prepare_image_custom_size():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        img = Image.new("RGB", (300, 300), (100, 100, 100))
        img.save(inp)
        result = prepare_image(inp, out, mode="photo", width=80, height=160)
        assert result.output_image.size == (80, 160)


def test_prepare_image_returns_stages():
    from ui.image_tools import prepare_image

    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.png")
        out = os.path.join(td, "output.png")
        prev = os.path.join(td, "stages")
        img = Image.new("RGB", (200, 400), (128, 128, 128))
        img.save(inp)
        result = prepare_image(inp, out, mode="photo", preview_dir=prev)
        assert "grayscale" in result.stages
        assert "contrast" in result.stages
        assert "dithered" in result.stages


# --- Dither ---


def test_floyd_steinberg():
    from ui.image_tools.dither import floyd_steinberg

    img = Image.new("L", (50, 50), 128)
    result = floyd_steinberg(img)
    assert result.mode == "L"
    assert result.size == (50, 50)


def test_floyd_steinberg_extremes():
    from ui.image_tools.dither import floyd_steinberg

    black = Image.new("L", (10, 10), 0)
    result = floyd_steinberg(black)
    pixels = list(result.get_flattened_data())
    assert all(p == 0 for p in pixels)

    white = Image.new("L", (10, 10), 255)
    result = floyd_steinberg(white)
    pixels = list(result.get_flattened_data())
    assert all(p == 255 for p in pixels)


def test_threshold_dither():
    from ui.image_tools.dither import threshold

    img = Image.new("L", (50, 50), 128)
    result = threshold(img, 100)
    assert result.mode == "L"
    pixels = list(result.get_flattened_data())
    assert all(p in (0, 255) for p in pixels)


def test_threshold_dither_levels():
    from ui.image_tools.dither import threshold

    img = Image.new("L", (10, 10), 128)
    r_low = threshold(img, 50)
    assert all(p == 255 for p in r_low.get_flattened_data())
    r_high = threshold(img, 200)
    assert all(p == 0 for p in r_high.get_flattened_data())


def test_ordered_dither():
    from ui.image_tools.dither import ordered_dither

    img = Image.new("L", (50, 50), 128)
    result = ordered_dither(img, size=4)
    assert result.mode == "L"
    assert result.size == (50, 50)


def test_ordered_dither_sizes():
    from ui.image_tools.dither import ordered_dither

    img = Image.new("L", (20, 20), 128)
    for size in (2, 4, 8):
        result = ordered_dither(img, size=size)
        assert result.size == (20, 20)


# --- Contact Sheet ---


def test_contact_sheet():
    from ui.preview.contact_sheet import render_contact_sheet

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "sheet.png")
        result = render_contact_sheet(output_path=path)
        assert os.path.exists(path)
        img = Image.open(path)
        assert img.size[0] > 0
        assert img.size[1] > 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
