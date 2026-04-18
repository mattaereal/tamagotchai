"""Layout composition for the status board."""
from typing import Dict, Any

from .theme import draw_box, draw_footer


def render_components(state: Dict[str, Any], display_cfg: Dict[str, Any]) -> None:
    """Render component grid – placeholder for flexible layout logic."""
    draw_box(display_cfg, "AI HEALTH", 0, 0)

    providers: list = state.get("providers", [])
    y = 2
    for p in providers:
        y = draw_box(display_cfg, f"[{p.get('provider_type', 'STATUSPAGE').upper()}] {p.get('name', '')}", 0, y)
        for comp in p.get("components", []):
            icon = comp.get("status", "UNKNOWN").ljust(3) if isinstance(comp.get("status"), str) else "[?]"
            y = draw_box(display_cfg, f"{icon} {comp.get('name', '')}", 4, y)

    draw_footer(display_cfg, state.get("last_refresh"), state.get("stale", False), y)
