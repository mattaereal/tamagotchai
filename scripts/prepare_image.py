#!/usr/bin/env python3
"""Convert images for e-paper display.

Usage:
    python scripts/prepare_image.py input.jpg output.png
    python scripts/prepare_image.py input.jpg output.png --mode photo
    python scripts/prepare_image.py input.jpg output.png --mode logo
    python scripts/prepare_image.py input.jpg output.png --mode portrait
    python scripts/prepare_image.py input.jpg output.png --mode mascot
    python scripts/prepare_image.py input.jpg output.png --contrast 2.0 --no-dither
    python scripts/prepare_image.py input.jpg output.png --preview-dir out/stages
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.image_tools import prepare_image, PRESETS


def main():
    parser = argparse.ArgumentParser(description="Convert images for e-paper display")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output PNG path")
    parser.add_argument(
        "--mode",
        "-m",
        default="photo",
        choices=list(PRESETS.keys()),
        help="Preset mode (default: photo)",
    )
    parser.add_argument(
        "--width", "-W", type=int, help="Target width (overrides preset)"
    )
    parser.add_argument(
        "--height", "-H", type=int, help="Target height (overrides preset)"
    )
    parser.add_argument(
        "--contrast", "-c", type=float, help="Contrast factor (overrides preset)"
    )
    parser.add_argument("--no-sharpen", action="store_true", help="Disable sharpening")
    parser.add_argument(
        "--method",
        choices=["floyd_steinberg", "ordered", "threshold"],
        help="Dithering/threshold method (overrides preset)",
    )
    parser.add_argument(
        "--threshold", type=int, help="Threshold level 0-255 (default: 128)"
    )
    parser.add_argument(
        "--preview-dir", "-p", help="Save intermediate stages to this directory"
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input file not found: {args.input}")
        sys.exit(1)

    sharpen = False if args.no_sharpen else None

    result = prepare_image(
        input_path=args.input,
        output_path=args.output,
        mode=args.mode,
        width=args.width,
        height=args.height,
        contrast=args.contrast,
        sharpen=sharpen,
        method=args.method,
        threshold_level=args.threshold,
        preview_dir=args.preview_dir,
    )

    print(f"Output: {result.output_path}")
    print(f"Size: {result.output_image.size}")
    print(f"Mode: {result.output_image.mode}")
    if result.stages:
        print(f"\nIntermediate stages:")
        for stage_name, stage_path in result.stages.items():
            print(f"  {stage_name}: {stage_path}")


if __name__ == "__main__":
    main()
