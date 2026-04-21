"""Canvas - core rendering surface for the 122x250 e-paper display.

Wraps a PIL 1-bit Image + ImageDraw with convenience methods
for the patterns used across all screen templates.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

W: int = 250
H: int = 122
MARGIN: int = 4


class Canvas:
    __slots__ = ("img", "draw", "w", "h")

    def __init__(self, width: int = W, height: int = H):
        self.img: Image.Image = Image.new("1", (width, height), 255)
        self.draw: ImageDraw.ImageDraw = ImageDraw.Draw(self.img)
        self.w: int = width
        self.h: int = height

    @property
    def content_left(self) -> int:
        return MARGIN

    @property
    def content_right(self) -> int:
        return self.w - MARGIN

    @property
    def content_top(self) -> int:
        return MARGIN

    @property
    def content_bottom(self) -> int:
        return self.h - MARGIN

    @property
    def content_width(self) -> int:
        return self.w - 2 * MARGIN

    def text(self, xy: tuple[int, int], text: str, fill: int = 0) -> None:
        self.draw.text(xy, text, fill=fill)

    def centered_text(self, y: int, text: str, fill: int = 0) -> None:
        bbox = self.draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        x = (self.w - tw) // 2
        self.draw.text((x, y), text, fill=fill)

    def right_text(self, y: int, text: str, fill: int = 0) -> None:
        bbox = self.draw.textbbox((0, 0), text)
        tw = bbox[2] - bbox[0]
        x = self.content_right - tw
        self.draw.text((x, y), text, fill=fill)

    def line(self, xy: tuple, fill: int = 0, width: int = 1) -> None:
        self.draw.line(xy, fill=fill, width=width)

    def hline(self, y: int, fill: int = 0) -> None:
        self.draw.line([(MARGIN, y), (self.w - MARGIN, y)], fill=fill)

    def rect(self, xy: tuple, outline: int = 0, fill=None) -> None:
        self.draw.rectangle(xy, outline=outline, fill=fill)

    def filled_rect(self, xy: tuple, fill: int = 0) -> None:
        self.draw.rectangle(xy, fill=fill)

    def ellipse(self, xy: tuple, outline: int = 0, fill=None, width: int = 1) -> None:
        self.draw.ellipse(xy, outline=outline, fill=fill, width=width)

    def arc(
        self, xy: tuple, start: int, end: int, fill: int = 0, width: int = 1
    ) -> None:
        self.draw.arc(xy, start=start, end=end, fill=fill, width=width)

    def point(self, xy: tuple, fill: int = 0) -> None:
        self.draw.point(xy, fill=fill)

    def paste(self, img: Image.Image, box: tuple[int, int]) -> None:
        self.img.paste(img, box)

    def truncate(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."

    def to_image(self) -> Image.Image:
        return self.img.copy()
