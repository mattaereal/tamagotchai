"""Rendering utilities."""
from typing import Dict, Any

from .layout import render_components


def render_state(state: Dict[str, Any], display_cfg: Dict[str, Any]) -> None:
    """Render full application state to display."""
    from ..display import get_display

    display = get_display(display_cfg)
    display.render(state)
    display.flush()
