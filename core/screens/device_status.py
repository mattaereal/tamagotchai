"""Device status screen (type: device_status).

Gathers local system vitals and renders them to the e-paper display.
No HTTP fetch -- all data comes from local system calls.
"""

import hashlib
import logging
import os
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig
from ui.canvas import Canvas
from ui import layout, MARGIN

logger = logging.getLogger(__name__)

APP_VERSION = "1.0.0"


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (OSError, IOError):
        return None


def _run_cmd(cmd: list[str], fallback: str = "--") -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
        return fallback
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return fallback


def _get_ip() -> str:
    out = _run_cmd(["nmcli", "-t", "-f", "DEVICE,IP4.ADDRESS", "device", "status"])
    if not out or out == "--":
        return "--"
    for line in out.split("\n"):
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == "wlan0" and parts[1]:
            addr = parts[1]
            if "/" in addr:
                addr = addr.split("/")[0]
            return addr
    return "--"


def _get_ssid() -> str:
    out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi", "list"])
    if not out or out == "--":
        return "--"
    for line in out.split("\n"):
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == "yes":
            return parts[1]
    return "--"


def _get_bssid() -> str:
    out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,BSSID", "dev", "wifi", "list"])
    if not out or out == "--":
        return "--"
    for line in out.split("\n"):
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == "yes":
            return parts[1]
    return "--"


def _get_wifi_status() -> str:
    out = _run_cmd(["nmcli", "networking", "connectivity", "check"])
    if out == "full":
        return "connected"
    elif out == "limited":
        return "limited"
    elif out == "none":
        return "offline"
    return "--"


def _get_signal() -> str:
    out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,SIGNAL", "dev", "wifi", "list"])
    if not out or out == "--":
        return "--"
    for line in out.split("\n"):
        parts = line.split(":")
        if len(parts) >= 2 and parts[0] == "yes":
            return f"{parts[1]}%"
    return "--"


def _get_cpu_temp() -> str:
    raw = _read_file("/sys/class/thermal/thermal_zone0/temp")
    if raw:
        try:
            temp_c = int(raw) / 1000.0
            return f"{temp_c:.1f}C"
        except ValueError:
            pass
    return "--"


def _get_uptime() -> str:
    raw = _read_file("/proc/uptime")
    if raw:
        try:
            seconds = float(raw.split()[0])
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            return f"{hours}h {minutes}m"
        except (ValueError, IndexError):
            pass
    return "--"


def _get_disk() -> str:
    try:
        usage = shutil.disk_usage("/")
        used_gb = usage.used / (1024**3)
        total_gb = usage.total / (1024**3)
        return f"{used_gb:.1f}/{total_gb:.0f}GB"
    except OSError:
        return "--"


def _get_memory() -> str:
    raw = _read_file("/proc/meminfo")
    if not raw:
        return "--"
    mem_total = None
    mem_available = None
    for line in raw.split("\n"):
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                mem_total = int(parts[1])
        elif line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2:
                mem_available = int(parts[1])
    if mem_total and mem_available is not None:
        used_mb = (mem_total - mem_available) // 1024
        total_mb = mem_total // 1024
        return f"{used_mb}/{total_mb}MB"
    return "--"


def _get_battery() -> tuple[str, bool]:
    try:
        import pisugar

        p = pisugar.PiSugarServer()
        level = p.get_battery_level()
        charging = p.get_battery_charging()
        return f"{level}%", charging
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"PiSugar read failed: {e}")

    try:
        import socket as sock

        s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        s.settimeout(2)
        s.connect("/tmp/pisugar-server.sock")
        s.sendall(b'{"get_battery_level": null}\n')
        resp = s.recv(1024).decode().strip()
        s.close()

        import json

        data = json.loads(resp)
        level = data.get("result", data.get("get_battery_level", "--"))
        if isinstance(level, (int, float)):
            level = f"{level}%"

        s2 = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        s2.settimeout(2)
        s2.connect("/tmp/pisugar-server.sock")
        s2.sendall(b'{"get_battery_charging": null}\n')
        resp2 = s2.recv(1024).decode().strip()
        s2.close()

        data2 = json.loads(resp2)
        charging = bool(data2.get("result", data2.get("get_battery_charging", False)))

        return str(level), charging
    except Exception as e:
        logger.debug(f"PiSugar socket read failed: {e}")

    return "--", False


def _get_pid() -> str:
    pid_file = "/tmp/tamagotchai.pid"
    raw = _read_file(pid_file)
    if raw:
        try:
            os.kill(int(raw), 0)
            return raw
        except (OSError, ValueError):
            pass
    return "not running"


class DeviceStatusScreen(Screen):
    def __init__(self, config: ScreenConfig):
        self._config = config
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._data: Dict[str, Any] = {}
        self._last_hash: Optional[str] = None

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def fetch(self, session: Any) -> None:
        battery_level, battery_charging = _get_battery()
        self._data = {
            "hostname": socket.gethostname(),
            "ip": _get_ip(),
            "ssid": _get_ssid(),
            "bssid": _get_bssid(),
            "wifi_status": _get_wifi_status(),
            "signal": _get_signal(),
            "cpu_temp": _get_cpu_temp(),
            "memory": _get_memory(),
            "disk": _get_disk(),
            "uptime": _get_uptime(),
            "battery": battery_level,
            "battery_charging": battery_charging,
            "pid": _get_pid(),
            "version": APP_VERSION,
        }

    def render(self, width: int, height: int) -> Image.Image:
        from ui.layouts import render as tpl_render

        img = tpl_render("device_status", self._data, canvas=Canvas(width, height))
        self._last_hash = self._data_hash()
        return img

    def has_changed(self) -> bool:
        if self._last_hash is None:
            return True
        return self._data_hash() != self._last_hash

    def _data_hash(self) -> str:
        raw = str(sorted(self._data.items()))
        return hashlib.md5(raw.encode()).hexdigest()
