"""OpenCode detail template -- dedicated single-agent screen.

Shows ALL available metadata fields. Uses the full 122x250 canvas
with visual grouping, separators, and two-column layouts where
possible. Nothing is hidden — everything renders.

If the fetch fails, shows a compact horizontal setup hint.
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
        return f"{minutes}m{secs:02d}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h{mins:02d}m"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 2] + ".."


def _render_content(c: Canvas, data: dict) -> None:
    """Render dense detail layout using full vertical space."""
    meta = data.get("metadata", {}) or {}
    max_x = c.w - MARGIN

    # --- Status Header Block (big, centered-ish) ---
    status = str(data.get("status", "")).lower()
    icon = _STATUS_ICONS.get(status, "[?]")
    y = 18

    # Status line: icon + status centered as a block
    status_text = f"{icon}  {status}" if status else icon
    c.text((MARGIN, y), status_text, fill=0)
    y += layout.LINE_H + 2

    # Divider under status
    c.hline(y, fill=0)
    y += 5

    # --- Task / Message ---
    msg = data.get("message", "")
    if msg:
        msg = _truncate(msg, 20)
        c.text((MARGIN, y), msg, fill=0)
        y += layout.LINE_H_SMALL + 1

    # --- Model (prominent, its own line) ---
    model = meta.get("model", "")
    if model:
        model_short = model.split("/")[-1] if "/" in str(model) else str(model)
        model_short = _truncate(model_short, 18)
        c.text((MARGIN, y), model_short, fill=0)
        y += layout.LINE_H_SMALL + 1

    # Divider
    c.hline(y, fill=0)
    y += 5

    # --- Token + Cost Row (side by side if possible) ---
    tok_in = meta.get("tokens_input")
    tok_out = meta.get("tokens_output")
    cost = meta.get("cost_usd")

    left_parts = []
    if tok_in is not None or tok_out is not None:
        t_in = _fmt_num(float(tok_in)) if tok_in is not None else "0"
        t_out = _fmt_num(float(tok_out)) if tok_out is not None else "0"
        left_parts.append(f"tok {t_in}/{t_out}")
    if cost is not None and float(cost) > 0:
        left_parts.append(f"${float(cost):.4f}")

    if left_parts:
        c.text((MARGIN, y), "  ".join(left_parts), fill=0)
        y += layout.LINE_H_SMALL + 1

    # --- Tool + Files + Msgs Row ---
    mid_parts = []
    tool = meta.get("tool_name", "")
    if tool:
        mid_parts.append(str(tool))
    files = meta.get("files_modified")
    if files is not None and int(files) > 0:
        mid_parts.append(f"{files}f")
    msgs = meta.get("message_count")
    if msgs is not None and int(msgs) > 0:
        mid_parts.append(f"{msgs}m")
    if mid_parts:
        c.text((MARGIN, y), " | ".join(mid_parts), fill=0)
        y += layout.LINE_H_SMALL + 1

    # --- Duration + Diff + Commits Row ---
    right_parts = []
    duration = meta.get("session_duration_ms")
    if duration:
        right_parts.append(_fmt_duration(int(duration)))
    added = meta.get("lines_added")
    removed = meta.get("lines_removed")
    if added or removed:
        diff_str = ""
        if added:
            diff_str += f"+{added}"
        if removed:
            diff_str += f"/-{removed}"
        right_parts.append(diff_str)
    commits = meta.get("commits")
    if commits is not None and int(commits) > 0:
        right_parts.append(f"{commits}c")
    if right_parts:
        c.text((MARGIN, y), " | ".join(right_parts), fill=0)
        y += layout.LINE_H_SMALL + 1

    # Divider
    c.hline(y, fill=0)
    y += 5

    # --- Project ---
    proj = meta.get("project", "")
    if proj:
        c.text((MARGIN, y), _truncate(str(proj), 16), fill=0)
        y += layout.LINE_H_SMALL + 1

    # --- Pending ---
    pending = data.get("pending", 0)
    if pending and int(pending) > 0:
        c.text((MARGIN, y), f"pending: {pending}", fill=0)
        y += layout.LINE_H_SMALL + 1

    # Fill remaining vertical space with heartbeat or just push footer down
    footer_y = c.h - layout.LINE_H - 2
    heartbeat = data.get("last_heartbeat", "")
    ts = ""
    if heartbeat:
        try:
            dt = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
            ts = dt.astimezone(timezone.utc).strftime("%H:%M:%S")
        except (ValueError, TypeError):
            pass
    if ts:
        c.text((MARGIN, footer_y), ts, fill=0)


def _render_hint(c: Canvas) -> None:
    """Render compact horizontal setup hint filling space better."""
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


@register("opencode")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "OpenCode")
    fetch_error = data.get("fetch_error", False)

    # Title
    c.text((MARGIN, 3), name, fill=0)
    c.hline(14, fill=0)

    if fetch_error:
        _render_hint(c)
    else:
        _render_content(c, data)

    return c.to_image()
