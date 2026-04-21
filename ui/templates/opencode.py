"""OpenCode detail template -- dedicated single-agent screen.

Renders a status header + configurable info_lines + footer.
All layout is delegated to the info_lines from config, so users
can comment/uncomment lines in screens.yml to show/hide fields.

If fetch fails, shows a bordered setup hint instead.
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


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 2] + ".."


@register("opencode")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "OpenCode")
    fetch_error = data.get("fetch_error", False)
    info_lines = data.get("info_lines", [])
    heartbeat = data.get("last_heartbeat", "")

    # Title
    c.text((MARGIN, 3), name, fill=0)
    c.hline(14, fill=0)

    if fetch_error:
        _render_hint(c)
        return c.to_image()

    y = 18
    max_y = c.h - layout.FOOTER_RESERVE - 2

    # Status line
    status = str(data.get("status", "")).lower()
    icon = _STATUS_ICONS.get(status, "[?]")
    msg = data.get("message", "")
    if status and msg:
        c.text((MARGIN, y), f"{icon}  {status}  |  {msg}", fill=0)
    elif status:
        c.text((MARGIN, y), f"{icon}  {status}", fill=0)
    elif msg:
        c.text((MARGIN, y), f"{icon}  {msg}", fill=0)
    else:
        c.text((MARGIN, y), icon, fill=0)
    y += layout.LINE_H_SMALL + 1

    # Divider under status
    if y + 2 < max_y:
        c.hline(y + 1, fill=0)
        y += 4

    # Info lines from config
    for line in info_lines:
        if y + layout.LINE_H_SMALL > max_y:
            layout.overflow_marker(c, y)
            break
        label = line.get("label", "")
        value = line.get("value", "")
        if label:
            text = f"{label}: {value}"
        else:
            text = value
        c.text((MARGIN, y), text, fill=0)
        y += layout.LINE_H_SMALL

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
    c.rect((MARGIN, y, c.w - MARGIN, y + 70), outline=0)

    hint_lines = [
        "[-] offline",
        "",
        "Install plugin:",
        "~/.config/opencode/",
        "plugins/tamagotchai.ts",
        "",
        "Then start opencode.",
    ]
    for line in hint_lines:
        if y + layout.LINE_H_SMALL > c.h - layout.FOOTER_RESERVE:
            break
        c.text((MARGIN + 4, y), line, fill=0)
        y += layout.LINE_H_SMALL

    footer_y = c.h - layout.LINE_H - 2
    c.text((MARGIN, footer_y), "check config/screens.yml", fill=0)
