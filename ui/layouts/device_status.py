"""Device status layout -- landscape OS monitor style.

Top bar: hostname + WiFi status
Grid: system vitals in compact columns with mini progress bars
Bottom: version + timestamp

Used by core/screens/device_status.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PIL import Image

from ..canvas import Canvas
from .. import layout, MARGIN
from . import register

_LINE_H = 11
_BAR_W = 50
_BAR_H = 6


def _draw_mini_bar(c: Canvas, x: int, y: int, pct: float) -> None:
    """Draw a compact progress bar."""
    c.rect((x, y, x + _BAR_W, y + _BAR_H), outline=0)
    fill_w = int((_BAR_W - 2) * max(0, min(1, pct)))
    if fill_w > 0:
        c.filled_rect((x + 1, y + 1, x + 1 + fill_w, y + _BAR_H - 1), fill=0)


def _parse_pct(text: str) -> float:
    """Try to extract a percentage from text like '85%' or '234/512MB'."""
    if "%" in text:
        try:
            return float(text.replace("%", "").strip()) / 100
        except ValueError:
            pass
    if "/" in text:
        parts = text.split("/")
        if len(parts) == 2:
            try:
                used = float(parts[0].strip())
                total = float(parts[1].strip().replace("MB", "").replace("GB", ""))
                if total > 0:
                    return used / total
            except ValueError:
                pass
    return -1  # no bar


@register("device_status")
def render(c: Canvas, data: dict) -> Image.Image:
    hostname = data.get("hostname", "unknown")
    ip = data.get("ip", "--")
    ssid = data.get("ssid", "--")
    wifi_status = data.get("wifi_status", "--")
    signal = data.get("signal", "--")
    cpu_temp = data.get("cpu_temp", "--")
    memory = data.get("memory", "--")
    disk = data.get("disk", "--")
    uptime = data.get("uptime", "--")
    battery = data.get("battery", "--")
    battery_charging = data.get("battery_charging", False)
    pid = data.get("pid", "--")
    version = data.get("version", "?")

    # Top bar: hostname left, WiFi right
    c.text((MARGIN, 3), hostname[:18], fill=0)

    wifi_icon = "[+]"
    ws = str(wifi_status).lower()
    if ws in ("full", "connected", "ok"):
        wifi_icon = "[+]"
    elif ws in ("limited", "degraded"):
        wifi_icon = "[!]"
    elif ws in ("no connectivity", "disconnected", "down", "offline"):
        wifi_icon = "[-]"
    else:
        wifi_icon = "[?]"

    wifi_text = f"WiFi {wifi_icon} {wifi_status}"
    if signal and str(signal) != "--":
        wifi_text += f"  {signal}"
    c.right_text(3, wifi_text)
    c.hline(14, fill=0)

    # Row 1: IP and SSID
    y = 18
    c.text((MARGIN, y), f"IP: {ip}", fill=0)
    c.right_text(y, f"SSID: {ssid}")
    y += _LINE_H + 2

    # Grid: system vitals with mini bars
    # Column positions
    col1_x = MARGIN
    col2_x = 90
    col3_x = 170

    def draw_metric(label: str, value: str, x: int, y: int) -> None:
        c.text((x, y), label, fill=0)
        c.text((x, y + _LINE_H), value[:10], fill=0)
        pct = _parse_pct(value)
        if pct >= 0:
            _draw_mini_bar(c, x, y + _LINE_H + 2, pct)

    # Row 2: CPU, Mem, Disk
    draw_metric("CPU", cpu_temp, col1_x, y)
    draw_metric("Mem", memory, col2_x, y)
    draw_metric("Disk", disk, col3_x, y)
    y += _LINE_H + _BAR_H + 8

    # Row 3: Uptime, Battery, PID
    bat_display = str(battery)
    if battery_charging:
        bat_display += " ~"
    draw_metric("Up", uptime, col1_x, y)
    draw_metric("Bat", bat_display, col2_x, y)
    c.text((col3_x, y), "PID", fill=0)
    c.text((col3_x, y + _LINE_H), str(pid), fill=0)
    y += _LINE_H + _BAR_H + 8

    # Bottom bar: version left, time right
    footer_y = c.h - _LINE_H - 2
    c.text((MARGIN, footer_y), f"v{version}", fill=0)
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    c.right_text(footer_y, now)

    return c.to_image()
