"""Contact sheet: render all templates in a grid for quick review."""

from __future__ import annotations

import os

from PIL import Image

from .. import W, H
from . import render_template, templates


def render_contact_sheet(output_path: str = "out/screens/contact_sheet.png") -> str:
    names = templates.names()
    if not names:
        raise RuntimeError("No templates registered")

    scale = 2
    cols = 4
    rows = (len(names) + cols - 1) // cols
    gap = 4
    label_h = 10

    cell_w = W * scale + gap
    cell_h = H * scale + gap + label_h

    sheet_w = cols * cell_w + gap
    sheet_h = rows * cell_h + gap

    sheet = Image.new("1", (sheet_w, sheet_h), 255)

    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)

    for i, name in enumerate(names):
        col = i % cols
        row = i // cols
        x = gap + col * cell_w
        y = gap + row * cell_h

        path = render_template(name)
        img = Image.open(path)
        img = img.resize((W * scale, H * scale), Image.NEAREST)
        sheet.paste(img, (x, y))

        label_y = y + H * scale + 1
        draw.text((x, label_y), name, fill=0)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sheet.save(output_path, format="PNG")
    return output_path
