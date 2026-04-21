"""OpenCode detail layout -- landscape single-agent screen.

Split-panel design:
  - Left: framed status icon box + name
  - Right: info lines (large fields alone, small fields paired)

If fetch fails, shows a bordered setup hint.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register

_STATUS_ICONS = {
    "idle": "[+]",
    "ok": "[+]",
    "working": "[!]",
    "waiting_input": "[!]",
    "stuck": "[-]",
    "error": "[-]",
    "offline": "[-]",
    "success": "[*]",
}

# Labels that get their own full line (important / wide)
_LARGE_LABELS = {"model", "message", "msg", "tool", "status", "project", "name"}

# Labels that can be paired on the same line (compact metrics)
_SMALL_LABELS = {"cost", "files", "msgs", "tok", "tokens", "duration", "commits", "diff", "pending"}

_LEFT_COL_W = 70
_RIGHT_COL_X = 78
_LINE_H = 11
_BOX_SIZE = 60


def _is_large(label: str) -> bool:
    return any(hint in label.lower() for hint in _LARGE_LABELS)


def _is_small(label: str) -> bool:
    return any(hint in label.lower() for hint in _SMALL_LABELS)


@register("opencode")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "OpenCode")
    fetch_error = data.get("fetch_error", False)
    info_lines = data.get("info_lines", [])
    heartbeat = data.get("last_heartbeat", "")
    status = str(data.get("status", "")).lower()
    message = data.get("message", "")

    # Title bar
    c.text((MARGIN, 3), name, fill=0)
    c.hline(14, fill=0)

    if fetch_error:
        _render_hint(c)
        return c.to_image()

    # Status line under title
    icon = _STATUS_ICONS.get(status, "[?]")
    status_text = f"{icon}  {status}" if status else icon
    if message:
        status_text += f"  |  {message}"
    c.text((MARGIN, 18), status_text, fill=0)
    c.hline(30, fill=0)

    # Left column: framed status box + name
    box_x = MARGIN + 5  # centered in 70px column
    box_y = 34
    c.rect((box_x, box_y, box_x + _BOX_SIZE, box_y + _BOX_SIZE), outline=0)
    c.rect((box_x + 2, box_y + 2, box_x + _BOX_SIZE - 2, box_y + _BOX_SIZE - 2), outline=0)

    # Large status icon centered in box
    icon_text = _STATUS_ICONS.get(status, "[?]")
    # Estimate icon width (~24px for 3 chars)
    icon_x = box_x + (_BOX_SIZE - 24) // 2
    icon_y = box_y + (_BOX_SIZE - 12) // 2
    c.text((icon_x, icon_y), icon_text, fill=0)

    # Name below box
    c.centered_text(box_y + _BOX_SIZE + 4, name[:10], fill=0)

    # Right column: info lines
    # Categorize into large and small
    large_lines = []
    small_lines = []
    for line in info_lines:
        lbl = line.get("label", "").lower()
        if _is_large(lbl):
            large_lines.append(line)
        elif _is_small(lbl):
            small_lines.append(line)
        else:
            large_lines.append(line)  # default to large for unknown labels

    y = 34
    max_y = c.h - layout.FOOTER_RESERVE - 2

    # Render large fields (one per line)
    for line in large_lines:
        if y + _LINE_H > max_y:
            break
        label = line.get("label", "")
        value = line.get("value", "")
        text = f"{label}: {value}" if label else value
        # Truncate to right column width
        text = c.truncate(text, 28)
        c.text((_RIGHT_COL_X, y), text, fill=0)
        y += _LINE_H

    # Render small fields (paired two per line)
    for i in range(0, len(small_lines), 2):
        if y + _LINE_H > max_y:
            break
        left = small_lines[i]
        right = small_lines[i + 1] if i + 1 < len(small_lines) else None

        left_text = f"{left.get('label', '')}: {left.get('value', '')}"
        c.text((_RIGHT_COL_X, y), left_text[:16], fill=0)

        if right:
            right_text = f"{right.get('label', '')}: {right.get('value', '')}"
            c.text((_RIGHT_COL_X + 84, y), right_text[:16], fill=0)
        y += _LINE_H

    # Footer: heartbeat time
    footer_y = c.h - layout.LINE_H - 2
    ts = ""
    if heartbeat:
        try:
            dt = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
            ts = dt.astimezone(timezone.utc).strftime("%H:%M:%S")
        except (ValueError, TypeError):
            pass
    if ts:
        c.text((MARGIN, footer_y), ts, fill=0)

    return c.to_image()


def _render_hint(c: Canvas) -> None:
    """Render compact setup hint when agent is unreachable."""
    y = 40

    # Draw a box around the hint area
    c.rect((MARGIN, y, c.w - MARGIN, y + 50), outline=0)

    hint_lines = [
        "[-] offline",
        "",
        "Install plugin:",
        "~/.config/opencode/plugins/",
        "Then start opencode.",
    ]
    for line in hint_lines:
        if y + layout.LINE_H_SMALL > c.h - layout.FOOTER_RESERVE:
            break
        c.text((MARGIN + 4, y), line, fill=0)
        y += layout.LINE_H_SMALL

    footer_y = c.h - layout.LINE_H - 2
    c.text((MARGIN, footer_y), "check config/screens.yml", fill=0)
