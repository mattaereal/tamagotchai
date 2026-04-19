"""Template registry for e-paper screen templates.

Maps template name strings to render functions.
Each render function takes (canvas, data) and returns a PIL Image.
"""

from __future__ import annotations

from typing import Callable, Dict

from PIL import Image

from ..canvas import Canvas

RenderFn = Callable[[Canvas, dict], Image.Image]

_REGISTRY: Dict[str, RenderFn] = {}


def register(name: str) -> Callable:
    def decorator(fn: RenderFn) -> RenderFn:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get(name: str) -> RenderFn:
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown template '{name}'. Available: {available}")
    return _REGISTRY[name]


def names() -> list[str]:
    return sorted(_REGISTRY.keys())


def render(
    name: str, data: dict | None = None, canvas: Canvas | None = None
) -> Image.Image:
    fn = get(name)
    c = canvas or Canvas()
    return fn(c, data or {})


from . import boot, setup, status_dashboard, detail, message, idle, error
