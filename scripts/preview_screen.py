#!/usr/bin/env python3
"""Preview e-paper screen templates as PNGs.

Usage:
    python scripts/preview_screen.py                       # all templates
    python scripts/preview_screen.py --template boot        # single template
    python scripts/preview_screen.py --contact-sheet        # all in one grid
    python scripts/preview_screen.py --output-dir out/      # custom output dir
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.preview import render_template, render_all
from ui.preview.contact_sheet import render_contact_sheet
from ui import templates


def main():
    parser = argparse.ArgumentParser(description="Preview e-paper screen templates")
    parser.add_argument("--template", "-t", help="Render a single template by name")
    parser.add_argument(
        "--contact-sheet",
        "-c",
        action="store_true",
        help="Render all templates in a contact sheet grid",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="out/screens",
        help="Output directory (default: out/screens)",
    )
    parser.add_argument("--list", action="store_true", help="List available templates")
    args = parser.parse_args()

    if args.list:
        print("Available templates:")
        for name in templates.names():
            print(f"  {name}")
        return

    if args.contact_sheet:
        out = os.path.join(args.output_dir, "contact_sheet.png")
        path = render_contact_sheet(output_path=out)
        print(f"Contact sheet: {path}")
        return

    if args.template:
        path = render_template(args.template, output_dir=args.output_dir)
        print(f"Rendered: {path}")
        return

    paths = render_all(output_dir=args.output_dir)
    for path in paths:
        print(f"Rendered: {path}")
    print(f"\n{len(paths)} templates rendered to {args.output_dir}/")


if __name__ == "__main__":
    main()
