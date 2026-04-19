"""Image preparation presets for different content types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Preset:
    name: str
    width: int
    height: int
    contrast: float
    sharpen: bool
    method: str
    threshold_level: int
    description: str


PRESETS = {
    "photo": Preset(
        name="photo",
        width=122,
        height=250,
        contrast=1.4,
        sharpen=True,
        method="floyd_steinberg",
        threshold_level=128,
        description="Full display, Floyd-Steinberg dither for photos",
    ),
    "logo": Preset(
        name="logo",
        width=122,
        height=250,
        contrast=2.0,
        sharpen=False,
        method="threshold",
        threshold_level=128,
        description="Full display, hard threshold for sharp logos/icons",
    ),
    "portrait": Preset(
        name="portrait",
        width=90,
        height=90,
        contrast=1.3,
        sharpen=True,
        method="floyd_steinberg",
        threshold_level=128,
        description="90x90 centered crop for tamagotchi sprites",
    ),
    "mascot": Preset(
        name="mascot",
        width=90,
        height=90,
        contrast=1.5,
        sharpen=True,
        method="floyd_steinberg",
        threshold_level=128,
        description="90x90 higher-contrast crop for mascot sprites",
    ),
}


def get_preset(name: str) -> Preset:
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    return PRESETS[name]
