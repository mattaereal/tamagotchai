"""Rendering utilities."""

from typing import Dict, Any, Union

from ai_health_board.config import DisplayConfig


def render_state(
    state: Dict[str, Any], display_cfg: Union[DisplayConfig, Dict[str, Any]]
) -> None:
    """Render full application state to display.

    Args:
        state: Dictionary with last_refresh, stale, providers
        display_cfg: Either a DisplayConfig object or a dict with display settings
    """
    from ..display import get_display

    display = get_display(display_cfg)
    display.render(state)
    display.flush()
