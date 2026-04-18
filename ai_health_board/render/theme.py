"""Theme and styling constants."""
from typing import Any, Dict, Optional

# Monochrome theme
COLOR_WHITE = 1
COLOR_BLACK = 0

BOX_PADDING = 1

def draw_box(cfg: Dict[str, Any], text: str, x: int, y: int) -> int:
    """Draw a text box on the display buffer. Returns next y position."""
    # In a real implementation this would draw to a display buffer
    # For mock/PIL backend, this is a no-op placeholder
    return y + 1

def draw_footer(cfg: Dict[str, Any], last_refresh: Optional[str], stale: bool, y: int) -> None:
    """Draw the footer line."""
    footer = "last ok" if last_refresh else "no data"
    if stale:
        footer += " | STALE"
    # In a real implementation this would draw to a display buffer
