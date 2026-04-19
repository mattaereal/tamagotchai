"""Image preparation pipeline for e-paper display.

Takes user images and converts them to 1-bit monochrome
output optimized for the 122x250 e-paper.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter

from .dither import floyd_steinberg, ordered_dither, threshold
from .presets import Preset, get_preset


@dataclass
class PreparationResult:
    output_path: str
    output_image: Image.Image
    stages: dict = field(default_factory=dict)


def prepare_image(
    input_path: str,
    output_path: str,
    mode: str = "photo",
    width: int | None = None,
    height: int | None = None,
    contrast: float | None = None,
    sharpen: bool | None = None,
    method: str | None = None,
    threshold_level: int | None = None,
    preview_dir: str | None = None,
) -> PreparationResult:
    preset = get_preset(mode)
    target_w = width or preset.width
    target_h = height or preset.height
    contrast_factor = contrast or preset.contrast
    do_sharpen = sharpen if sharpen is not None else preset.sharpen
    dither_method = method or preset.method
    t_level = threshold_level or preset.threshold_level

    img = Image.open(input_path)

    img = _crop_to_fit(img, target_w, target_h)

    img = img.convert("L")

    if preview_dir:
        os.makedirs(preview_dir, exist_ok=True)
        img.save(os.path.join(preview_dir, "1_grayscale.png"))

    if contrast_factor != 1.0:
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(contrast_factor)
        if preview_dir:
            img.save(os.path.join(preview_dir, "2_contrast.png"))

    if do_sharpen:
        img = img.filter(ImageFilter.SHARPEN)
        if preview_dir:
            img.save(os.path.join(preview_dir, "3_sharpen.png"))

    if dither_method == "floyd_steinberg":
        img = floyd_steinberg(img)
    elif dither_method == "ordered":
        img = ordered_dither(img)
    elif dither_method == "threshold":
        img = threshold(img, t_level)
    else:
        img = floyd_steinberg(img)

    if preview_dir:
        img.save(os.path.join(preview_dir, "4_dithered.png"))

    result = img.convert("1")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    result.save(output_path, format="PNG")

    stages = {}
    if preview_dir:
        stages["grayscale"] = os.path.join(preview_dir, "1_grayscale.png")
        stages["contrast"] = os.path.join(preview_dir, "2_contrast.png")
        stages["sharpen"] = os.path.join(preview_dir, "3_sharpen.png")
        stages["dithered"] = os.path.join(preview_dir, "4_dithered.png")

    return PreparationResult(
        output_path=output_path,
        output_image=result,
        stages=stages,
    )


def _crop_to_fit(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    if src_ratio > tgt_ratio:
        new_h = src_h
        new_w = int(src_h * tgt_ratio)
    else:
        new_w = src_w
        new_h = int(src_w / tgt_ratio)

    left = (src_w - new_w) // 2
    top = (src_h - new_h) // 2

    img = img.crop((left, top, left + new_w, top + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)
