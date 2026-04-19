#!/usr/bin/env python3
"""Render all ui/ templates to PNGs for quick visual review.

Usage:
    python scripts/preview_all.py
    python scripts/preview_all.py --contact-sheet
    python scripts/preview_all.py --output-dir out/preview
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.preview import render_all
from ui.preview.contact_sheet import render_contact_sheet


def main():
    parser = argparse.ArgumentParser(
        description="Render all ui/ templates to PNG files"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="out/screens",
        help="Directory for individual template PNGs (default: out/screens)",
    )
    parser.add_argument(
        "--contact-sheet",
        action="store_true",
        help="Also render a contact sheet grid",
    )
    parser.add_argument(
        "--contact-sheet-path",
        default="out/screens/contact_sheet.png",
        help="Contact sheet output path (default: out/screens/contact_sheet.png)",
    )
    args = parser.parse_args()

    print(f"Rendering templates to {args.output_dir}/")
    paths = render_all(output_dir=args.output_dir)
    for p in paths:
        print(f"  {os.path.basename(p)}")

    if args.contact_sheet:
        print(f"\nRendering contact sheet -> {args.contact_sheet_path}")
        render_contact_sheet(output_path=args.contact_sheet_path)

    print(f"\nDone. {len(paths)} template(s) rendered.")


if __name__ == "__main__":
    main()
