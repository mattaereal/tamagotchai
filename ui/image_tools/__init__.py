"""Image preparation tools for e-paper display.

Converts user images into 1-bit monochrome output optimized
for the 122x250 Waveshare V3 e-paper display.
"""

from .prepare import prepare_image, PreparationResult
from .presets import PRESETS, get_preset

__all__ = ["prepare_image", "PreparationResult", "PRESETS", "get_preset"]
