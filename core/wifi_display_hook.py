"""Display hook for the Wi-Fi onboarding subsystem.

When the wifi-setup service activates, it calls show_setup_info()
to render setup instructions on the e-paper display.

This module is loaded via WIFI_SETUP_DISPLAY_HOOK=core.wifi_display_hook
set in the wifi-setup systemd service environment.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

_DISPLAY = None


def _get_display():
    global _DISPLAY
    if _DISPLAY is not None:
        return _DISPLAY
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from core.config import load_config
        from core.display import get_display

        config = load_config(os.path.join(os.path.dirname(__file__), "..", "config"))
        _DISPLAY = get_display(config.display)
        return _DISPLAY
    except Exception as e:
        logger.warning(f"Could not initialize display for wifi hook: {e}")
        return None


def show_setup_info(line1: str, line2: str, line3: str) -> None:
    """Render wifi setup info on the e-paper display.

    Called by provisioning.hotspot._display_hook() when entering/leaving setup mode.
    With empty strings, clears the display.
    """
    display = _get_display()
    if display is None:
        return

    try:
        from ui.canvas import Canvas
        from ui.layouts.setup import render

        data = {}
        if line1 or line2 or line3:
            if "SSID:" in line2:
                data["ssid"] = line2.replace("SSID: ", "").replace("SSID:", "").strip()
            if "http" in line3:
                data["url"] = line3.strip()
        else:
            data = {"ssid": "", "url": ""}

        c = Canvas(display.width, display.height)
        img = render(c, data)
        display.render_image(img)
        logger.info(f"Display hook: rendered '{line1}' / '{line2}' / '{line3}'")
    except Exception as e:
        logger.warning(f"Display hook render failed: {e}")
