"""Dithering and thresholding algorithms for 1-bit conversion."""

from __future__ import annotations

import numpy as np
from PIL import Image


def threshold(img: Image.Image, level: int = 128) -> Image.Image:
    """Hard threshold: pixels above level become white, below become black."""
    arr = np.array(img.convert("L"), dtype=np.uint8)
    result = np.where(arr >= level, 255, 0).astype(np.uint8)
    return Image.fromarray(result, mode="L")


def floyd_steinberg(img: Image.Image) -> Image.Image:
    """Floyd-Steinberg error-diffusion dithering."""
    arr = np.array(img.convert("L"), dtype=np.float64)
    h, w = arr.shape

    for y in range(h):
        for x in range(w):
            old = arr[y, x]
            new = 0.0 if old < 128 else 255.0
            arr[y, x] = new
            err = old - new
            if x + 1 < w:
                arr[y, x + 1] += err * 7 / 16
            if y + 1 < h:
                if x - 1 >= 0:
                    arr[y + 1, x - 1] += err * 3 / 16
                arr[y + 1, x] += err * 5 / 16
                if x + 1 < w:
                    arr[y + 1, x + 1] += err * 1 / 16

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")


def ordered_dither(img: Image.Image, size: int = 4) -> Image.Image:
    """Ordered (Bayer) dithering."""
    if size == 2:
        matrix = np.array([[0, 2], [3, 1]]) * (256 / 4)
    elif size == 4:
        matrix = np.array(
            [
                [0, 8, 2, 10],
                [12, 4, 14, 6],
                [3, 11, 1, 9],
                [15, 7, 13, 5],
            ]
        ) * (256 / 16)
    elif size == 8:
        m4 = np.array(
            [
                [0, 8, 2, 10],
                [12, 4, 14, 6],
                [3, 11, 1, 9],
                [15, 7, 13, 5],
            ]
        ) * (256 / 16)
        matrix = np.zeros((8, 8))
        for r in range(2):
            for c in range(2):
                matrix[r * 4 : r * 4 + 4, c * 4 : c * 4 + 4] = m4 + (r * 2 + c) * 64
    else:
        matrix = np.array([[0, 2], [3, 1]]) * (256 / 4)

    arr = np.array(img.convert("L"), dtype=np.float64)
    h, w = arr.shape
    mh, mw = matrix.shape

    for y in range(h):
        for x in range(w):
            threshold_val = matrix[y % mh, x % mw]
            arr[y, x] = 255.0 if arr[y, x] > threshold_val else 0.0

    return Image.fromarray(arr.astype(np.uint8), mode="L")
