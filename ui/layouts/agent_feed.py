"""Agent feed layout -- landscape compact rows.

Each agent renders as a horizontal card:
  Row 1: icon + name + status + message
  Row 2: model + cost + tokens (compact metadata bar)

Used by core/screens/agent_feed.py.
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

_LINE_H = 11
_AGENT_H = 24  # 2 lines + gap


def _format_meta_compact(metadata: dict) -> str:
    """Build a compact metadata string for the second row."""
    if not metadata:
        return ""

    parts = []
    model = metadata.get("model")
    if model and isinstance(model, str):
        model_short = model.split("/")[-1]
        if len(model_short) > 10:
            model_short = model_short[:8] + ".."
        parts.append(model_short)

    cost = metadata.get("cost_usd")
    if cost is not None and float(cost) > 0:
        import math
        c = float(cost)
        rounded = math.ceil(c * 100) / 100
        parts.append(f"${rounded:.2f}")

    tokens = metadata.get("tokens_total")
    if tokens is None:
        tokens_in = metadata.get("tokens_input", 0) or 0
        tokens_out = metadata.get("tokens_output", 0) or 0
        tokens = tokens_in + tokens_out
    if tokens and int(tokens) > 0:
        val = float(tokens)
        if val >= 1_000_000:
            parts.append(f"{val / 1_000_000:.1f}M tok")
        elif val >= 1_000:
            parts.append(f"{val / 1_000:.1f}K tok")
        else:
            parts.append(f"{int(val)} tok")

    if not parts:
        files = metadata.get("files_modified")
        if files and int(files) > 0:
            parts.append(f"{files} file{'s' if int(files) > 1 else ''}")
        msgs = metadata.get("message_count")
        if msgs and int(msgs) > 0:
            parts.append(f"{msgs} msg{'s' if int(msgs) > 1 else ''}")

    return "   ".join(parts[:3])


@register("agent_feed")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Agents")
    agents = data.get("agents", [])
    num_agents = data.get("num_agents", len(agents))

    # Title bar
    c.text((MARGIN, 3), name, fill=0)
    c.right_text(3, str(num_agents))
    c.hline(14, fill=0)

    y = 18
    for agent in agents:
        if y + _AGENT_H > c.h - layout.FOOTER_RESERVE:
            layout.overflow_marker(c, y)
            break

        status = str(agent.get("status", "")).lower()
        if agent.get("fetch_error"):
            status = "offline"
        icon = _STATUS_ICONS.get(status, "[?]")

        agent_name = agent.get("name", "?")
        if len(agent_name) > 10:
            agent_name = agent_name[:7] + "..."

        msg = agent.get("message", "")
        if len(msg) > 18:
            msg = msg[:15] + "..."

        # Row 1: icon + name + status + message
        row1 = f"{icon} {agent_name}"
        if status and status not in ("idle", "ok"):
            row1 += f"  {status}"
        if msg:
            row1 += f"  |  {msg}"
        c.text((MARGIN, y), c.truncate(row1, 40), fill=0)
        y += _LINE_H

        # Row 2: metadata bar
        meta = _format_meta_compact(agent.get("metadata", {}))
        if meta:
            c.text((MARGIN + 12, y), meta, fill=0)
        y += _LINE_H + 2

        # Separator
        if y + 2 < c.h - layout.FOOTER_RESERVE:
            c.hline(y - 1, fill=0)

    # Hint when all agents failed
    show_hint = data.get("show_hint", False)
    if show_hint and y + _LINE_H * 4 <= c.h - layout.FOOTER_RESERVE:
        y += 4
        hint_lines = [
            "No agent data.",
            "Install: ~/.config/opencode/plugins/tamagotchai.ts",
            "Check URL in config/screens.yml",
        ]
        for line in hint_lines:
            if y + _LINE_H > c.h - layout.FOOTER_RESERVE:
                break
            c.text((MARGIN, y), line, fill=0)
            y += _LINE_H

    # Footer
    footer_y = c.h - layout.LINE_H - 2
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    c.text((MARGIN, footer_y), f"{num_agents} agent(s) | {now}", fill=0)

    return c.to_image()
