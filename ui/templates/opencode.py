"""OpenCode detail template -- dedicated single-agent screen.

Shows ALL available metadata fields in a dense vertical layout.
No sprite -- pure information density. 122x250 optimized.

If the fetch fails, shows a compact horizontal setup hint
instead of the full data block.
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


def _fmt_num(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def _fmt_duration(ms: int | None) -> str:
    if not ms or ms <= 0:
        return ""
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 2] + ".."


def _render_content(c: Canvas, data: dict, start_y: int) -> int:
    """Render the full data block. Returns next y."""
    y = start_y
    max_y = c.h - layout.FOOTER_RESERVE - 2

    meta = data.get("metadata", {}) or {}

    # Status line with icon
    status = str(data.get("status", "")).lower()
    icon = _STATUS_ICONS.get(status, "[?]")
    status_text = f"{icon}  {status}" if status else icon
    c.text((MARGIN, y), status_text, fill=0)
    y += layout.LINE_H_SMALL

    # Task / message
    msg = data.get("message", "")
    if msg:
        msg = _truncate(msg, 20)
        c.text((MARGIN + 8, y), msg, fill=0)
        y += layout.LINE_H_SMALL

    # Divider
    if y + 2 < max_y:
        c.hline(y + 1, fill=0)
        y += 4

    # Model
    model = meta.get("model", "")
    if model and y + layout.LINE_H_SMALL < max_y:
        model_short = model.split("/")[-1] if "/" in str(model) else str(model)
        model_short = _truncate(model_short, 18)
        c.text((MARGIN, y), f"model: {model_short}", fill=0)
        y += layout.LINE_H_SMALL

    # Tokens (in / out)
    tok_in = meta.get("tokens_input")
    tok_out = meta.get("tokens_output")
    if (tok_in or tok_out) and y + layout.LINE_H_SMALL < max_y:
        parts = []
        if tok_in is not None:
            parts.append(f"in {_fmt_num(float(tok_in))}")
        if tok_out is not None:
            parts.append(f"out {_fmt_num(float(tok_out))}")
        c.text((MARGIN, y), f"tok: {'  '.join(parts)}", fill=0)
        y += layout.LINE_H_SMALL

    # Cost
    cost = meta.get("cost_usd")
    if cost is not None and float(cost) > 0 and y + layout.LINE_H_SMALL < max_y:
        c.text((MARGIN, y), f"cost: ${float(cost):.4f}", fill=0)
        y += layout.LINE_H_SMALL

    # Tool + files
    tool = meta.get("tool_name", "")
    files = meta.get("files_modified")
    if (tool or files) and y + layout.LINE_H_SMALL < max_y:
        parts = []
        if tool:
            parts.append(str(tool))
        if files is not None and int(files) > 0:
            parts.append(f"{files} file{'s' if int(files) > 1 else ''}")
        c.text((MARGIN, y), f"tool: {' / '.join(parts)}", fill=0)
        y += layout.LINE_H_SMALL

    # Messages + duration
    msgs = meta.get("message_count")
    duration = meta.get("session_duration_ms")
    if (msgs or duration) and y + layout.LINE_H_SMALL < max_y:
        parts = []
        if msgs is not None and int(msgs) > 0:
            parts.append(f"{msgs} msg{'s' if int(msgs) > 1 else ''}")
        if duration:
            parts.append(_fmt_duration(int(duration)))
        c.text((MARGIN, y), f"activity: {' / '.join(parts)}", fill=0)
        y += layout.LINE_H_SMALL

    # Lines added/removed
    added = meta.get("lines_added")
    removed = meta.get("lines_removed")
    if (added or removed) and y + layout.LINE_H_SMALL < max_y:
        parts = []
        if added:
            parts.append(f"+{added}")
        if removed:
            parts.append(f"-{removed}")
        c.text((MARGIN, y), f"diff: {'  '.join(parts)}", fill=0)
        y += layout.LINE_H_SMALL

    # Commits
    commits = meta.get("commits")
    if commits is not None and int(commits) > 0 and y + layout.LINE_H_SMALL < max_y:
        c.text((MARGIN, y), f"commits: {commits}", fill=0)
        y += layout.LINE_H_SMALL

    # Project
    proj = meta.get("project", "")
    if proj and y + layout.LINE_H_SMALL < max_y:
        c.text((MARGIN, y), f"project: {_truncate(str(proj), 14)}", fill=0)
        y += layout.LINE_H_SMALL

    return y


def _render_hint(c: Canvas, start_y: int) -> int:
    """Render compact horizontal setup hint. Returns next y."""
    y = start_y
    max_y = c.h - layout.FOOTER_RESERVE - 2

    hint_lines = [
        "[-] offline | install plugin:",
        "~/.config/opencode/plugins/",
        "tamagotchai.ts | start opencode",
    ]
    for line in hint_lines:
        if y + layout.LINE_H_SMALL > max_y:
            break
        c.text((MARGIN, y), line, fill=0)
        y += layout.LINE_H_SMALL

    return y


@register("opencode")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "OpenCode")
    fetch_error = data.get("fetch_error", False)
    heartbeat = data.get("last_heartbeat", "")

    # Title
    c.text((MARGIN, 3), name, fill=0)
    c.hline(14, fill=0)

    y = 18

    if fetch_error:
        y = _render_hint(c, y)
    else:
        y = _render_content(c, data, y)

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
