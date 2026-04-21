"""Agent feed template -- live data rendering.

Renders a compact row per agent: icon + name + status + message + metadata.
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


def _fmt_num(n: float) -> str:
    """Compact number formatter (e.g. 1200 -> 1.2k)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))


def _format_meta(metadata: dict) -> str:
    """Build a compact metadata string from known keys.

    Picks the most informative combination that fits within ~20 chars.
    Falls back to files_modified or message_count if no cost/tokens.
    """
    if not metadata:
        return ""

    MAX_LEN = 22

    model = metadata.get("model")
    model_short = ""
    if model and isinstance(model, str):
        model_short = model.split("/")[-1]
        if len(model_short) > 8:
            model_short = model_short[:6] + ".."

    tokens = metadata.get("tokens_total")
    if tokens is None:
        tokens_in = metadata.get("tokens_input", 0) or 0
        tokens_out = metadata.get("tokens_output", 0) or 0
        tokens = tokens_in + tokens_out
    tokens_str = ""
    if tokens and int(tokens) > 0:
        tokens_str = f"{_fmt_num(float(tokens))} tok"

    cost = metadata.get("cost_usd")
    cost_str = ""
    if cost is not None and float(cost) > 0:
        cost_str = f"${float(cost):.3f}"

    # Primary candidates (model / tokens / cost)
    candidates = [
        f"{model_short}  {cost_str}",
        f"{tokens_str}  {cost_str}",
        f"{model_short}  {tokens_str}",
        model_short,
        tokens_str,
        cost_str,
    ]

    for candidate in candidates:
        cleaned = candidate.strip()
        if cleaned and len(cleaned) <= MAX_LEN:
            return cleaned

    # Fallbacks for agents without cost tracking
    files = metadata.get("files_modified")
    if files and int(files) > 0:
        return f"{files} file{'s' if int(files) > 1 else ''}"

    msgs = metadata.get("message_count")
    if msgs and int(msgs) > 0:
        return f"{msgs} msg{'s' if int(msgs) > 1 else ''}"

    proj = metadata.get("project")
    if proj and isinstance(proj, str) and len(proj) <= MAX_LEN:
        return proj

    return ""


@register("agent_feed")
def render(c: Canvas, data: dict) -> Image.Image:
    name = data.get("name", "Agents")
    agents = data.get("agents", [])
    num_agents = data.get("num_agents", len(agents))

    c.text((MARGIN, 3), name, fill=0)
    c.hline(14, fill=0)

    y = 18
    for agent in agents:
        msg = agent.get("message", "")
        meta = _format_meta(agent.get("metadata", {}))

        # Estimate height needed for this agent
        agent_h = layout.LINE_H
        if msg:
            agent_h += layout.LINE_H_SMALL
        if meta:
            agent_h += layout.LINE_H_SMALL

        if y + agent_h > c.h - layout.FOOTER_RESERVE:
            layout.overflow_marker(c, y)
            break

        agent_name = agent.get("name", "?")
        if len(agent_name) > 12:
            agent_name = agent_name[:9] + "..."

        status = str(agent.get("status", "")).lower()
        if agent.get("fetch_error"):
            status = "offline"
        icon = _STATUS_ICONS.get(status, "[?]")

        row = f"{icon} {agent_name}"
        if status and status not in ("idle", "ok"):
            row += f"  {status}"
        c.text((MARGIN, y), row, fill=0)
        y += layout.LINE_H

        if msg:
            if len(msg) > 22:
                msg = msg[:19] + "..."
            c.text((MARGIN + 8, y), msg, fill=0)
            y += layout.LINE_H_SMALL

        if meta:
            if len(meta) > 22:
                meta = meta[:19] + "..."
            c.text((MARGIN + 8, y), meta, fill=0)
            y += layout.LINE_H_SMALL

    # If every agent failed, show quick setup hint
    show_hint = data.get("show_hint", False)
    if show_hint and y + layout.LINE_H * 6 <= c.h - layout.FOOTER_RESERVE:
        y += 4
        c.hline(y, fill=0)
        y += 6
        hint_lines = [
            "No agent data.",
            "Install plugin:",
            "  ~/.config/opencode/",
            "  plugins/tamagotchai.ts",
            "Check URL in",
            "  config/screens.yml",
        ]
        for line in hint_lines:
            if y + layout.LINE_H_SMALL > c.h - layout.FOOTER_RESERVE:
                break
            c.text((MARGIN, y), line, fill=0)
            y += layout.LINE_H_SMALL

    # If every agent failed, show quick setup hint
    show_hint = data.get("show_hint", False)
    if show_hint and y + layout.LINE_H * 6 <= c.h - layout.FOOTER_RESERVE:
        y += 4
        c.hline(y, fill=0)
        y += 6
        hint_lines = [
            "No agent data.",
            "Install plugin:",
            "  ~/.config/opencode/",
            "  plugins/tamagotchai.ts",
            "Check URL in",
            "  config/screens.yml",
        ]
        for line in hint_lines:
            if y + layout.LINE_H_SMALL > c.h - layout.FOOTER_RESERVE:
                break
            c.text((MARGIN, y), line, fill=0)
            y += layout.LINE_H_SMALL

    footer_y = c.h - layout.LINE_H - 2
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    c.text((MARGIN, footer_y), f"{num_agents} agent(s) | {now}", fill=0)

    return c.to_image()
