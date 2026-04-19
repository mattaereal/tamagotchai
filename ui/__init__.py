"""UI subsystem for the 122x250 monochrome e-paper display.

Public API:
    Canvas  - core rendering surface
    W, H    - native panel dimensions (122, 250)
    MARGIN  - default content margin (4)
"""

from .canvas import Canvas, W, H, MARGIN

__all__ = ["Canvas", "W", "H", "MARGIN"]
