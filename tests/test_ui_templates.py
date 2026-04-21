"""Tests for ui.layouts and the screen-cycling integration."""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image


# --- Template Registry ---


def test_template_registry():
    from ui.layouts import names

    n = names()
    assert "boot" in n
    assert "setup" in n
    assert "status_dashboard" in n
    assert "detail" in n
    assert "message" in n
    assert "idle" in n
    assert "error" in n
    assert "device_status" in n
    assert "status_board" in n
    assert "tamagotchi" in n
    assert "agent_feed" in n
    assert "opencode" in n


def test_render_boot():
    from ui.layouts import render

    img = render("boot", {"name": "Test", "version": "2.0"})
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_setup():
    from ui.layouts import render

    img = render("setup")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_status_dashboard():
    from ui.layouts import render

    img = render("status_dashboard")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_status_dashboard_with_categories():
    from ui.layouts import render

    data = {
        "name": "AI Status",
        "timestamp": "14:32:05",
        "categories": [
            {
                "name": "Claude",
                "icon": "anthropic",
                "items": [
                    {"label": "API", "status": "OK"},
                    {"label": "Code", "status": "DEGRADED"},
                ],
            },
            {
                "name": "OpenAI",
                "items": [
                    {"label": "ChatGPT", "status": "DOWN"},
                ],
            },
        ],
    }
    img = render("status_dashboard", data)
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_status_dashboard_overflow():
    from ui.layouts import render

    categories = []
    for i in range(20):
        categories.append(
            {
                "name": f"Cat{i}",
                "items": [{"label": f"item{j}", "status": "OK"} for j in range(5)],
            }
        )
    img = render("status_dashboard", {"categories": categories})
    assert img.size == (250, 122)


def test_render_detail():
    from ui.layouts import render

    img = render("detail")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_detail_with_metrics():
    from ui.layouts import render

    data = {
        "name": "Claude API",
        "status": "DEGRADED",
        "metrics": [
            {"label": "latency", "value": "340ms"},
            {"label": "uptime", "value": "99.2%"},
        ],
        "last_check": "14:32",
    }
    img = render("detail", data)
    assert img.size == (250, 122)


def test_render_message():
    from ui.layouts import render

    img = render("message")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_message_string_body():
    from ui.layouts import render

    img = render("message", {"title": "WARN", "body": "Single line"})
    assert img.size == (250, 122)


def test_render_message_no_title():
    from ui.layouts import render

    img = render("message", {"body": ["Line 1", "Line 2"]})
    assert img.size == (250, 122)


def test_render_idle():
    from ui.layouts import render

    img = render("idle")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_idle_with_sprite():
    from ui.layouts import render

    sprite = Image.new("1", (90, 90), 255)
    img = render("idle", {"name": "Bot", "mood": "working", "sprite": sprite})
    assert img.size == (250, 122)


def test_render_idle_moods():
    from ui.layouts import render

    for mood in ("idle", "working", "error"):
        img = render("idle", {"mood": mood})
        assert img.size == (250, 122)


def test_render_error():
    from ui.layouts import render

    img = render("error")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_error_with_detail():
    from ui.layouts import render

    img = render(
        "error",
        {
            "message": "Timeout",
            "detail": "Connection to upstream server failed after 10 seconds",
            "last_ok": "14:30",
        },
    )
    assert img.size == (250, 122)


def test_render_device_status():
    from ui.layouts import render

    img = render("device_status")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_device_status_with_data():
    from ui.layouts import render

    img = render(
        "device_status",
        {
            "hostname": "test.local",
            "ip": "10.0.0.1",
            "ssid": "TestNet",
            "bssid": "AA:BB:CC:DD:EE:FF",
            "wifi_status": "connected",
            "signal": "90%",
            "cpu_temp": "52.3C",
            "memory": "234/512MB",
            "disk": "3.2/28GB",
            "uptime": "2d 4h 32m",
            "battery": "87%",
            "battery_charging": True,
            "pid": "12345",
            "version": "1.0.0",
        },
    )
    assert img.size == (250, 122)


def test_render_status_board():
    from ui.layouts import render

    img = render("status_board")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_status_board_with_data():
    from ui.layouts import render

    img = render(
        "status_board",
        {
            "name": "AI Health",
            "timestamp": "14:32:05",
            "categories": [
                {
                    "name": "Claude",
                    "icon": "anthropic",
                    "items": [
                        {"label": "AI", "status": "OK"},
                        {"label": "API", "status": "DEGRADED"},
                    ],
                },
                {
                    "name": "OpenAI",
                    "icon": "openai",
                    "items": [
                        {"label": "App", "status": "DOWN"},
                    ],
                },
            ],
            "footer_text": "ok",
        },
    )
    assert img.size == (250, 122)


def test_render_tamagotchi():
    from ui.layouts import render

    img = render("tamagotchi")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_tamagotchi_with_data():
    from ui.layouts import render

    img = render(
        "tamagotchi",
        {
            "name": "Lotus",
            "mood": "working",
            "frame": 0,
            "sprites": {},
            "info_lines": [
                {"label": "status", "value": "working"},
                {"label": "pending", "value": "3"},
            ],
            "fetch_error": False,
            "last_checked": "2026-04-19T14:32:05+00:00",
        },
    )
    assert img.size == (250, 122)


def test_render_tamagotchi_fetch_error():
    from ui.layouts import render

    img = render(
        "tamagotchi",
        {
            "name": "Lotus",
            "mood": "error",
            "frame": 0,
            "sprites": {},
            "info_lines": [],
            "fetch_error": True,
            "last_checked": "",
        },
    )
    assert img.size == (250, 122)


def test_render_agent_feed():
    from ui.layouts import render

    img = render("agent_feed")
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_agent_feed_with_data():
    from ui.layouts import render

    img = render(
        "agent_feed",
        {
            "name": "Agents",
            "agents": [
                {
                    "name": "OpenCode",
                    "status": "working",
                    "message": "Coding",
                    "fetch_error": False,
                    "metadata": {
                        "model": "claude-3.7-sonnet",
                        "tokens_total": 1580,
                        "cost_usd": 0.0042,
                    },
                },
                {
                    "name": "Cursor",
                    "status": "idle",
                    "message": "",
                    "fetch_error": False,
                },
                {
                    "name": "Lotus",
                    "status": "error",
                    "message": "Crashed",
                    "fetch_error": True,
                },
            ],
            "num_agents": 3,
        },
    )
    assert img.size == (250, 122)


def test_render_agent_feed_metadata_only():
    from ui.layouts import render

    img = render(
        "agent_feed",
        {
            "name": "Agents",
            "agents": [
                {
                    "name": "OpenCode",
                    "status": "working",
                    "message": "",
                    "fetch_error": False,
                    "metadata": {
                        "model": "anthropic/claude-3.7-sonnet",
                        "tokens_input": 1240,
                        "tokens_output": 340,
                        "cost_usd": 0.0042,
                        "project": "tamagotchai",
                        "message_count": 3,
                        "files_modified": 2,
                    },
                },
            ],
            "num_agents": 1,
        },
    )
    assert img.size == (250, 122)


def test_render_agent_feed_fallback_metadata():
    from ui.layouts import render

    img = render(
        "agent_feed",
        {
            "name": "Agents",
            "agents": [
                {
                    "name": "Hermes",
                    "status": "working",
                    "message": "",
                    "fetch_error": False,
                    "metadata": {
                        "project": "myproject",
                        "files_modified": 5,
                        "message_count": 12,
                    },
                },
            ],
            "num_agents": 1,
        },
    )
    assert img.size == (250, 122)


def test_render_agent_feed_show_hint():
    from ui.layouts import render

    # When all agents failed, show_hint triggers setup instructions
    img = render(
        "agent_feed",
        {
            "name": "OpenCode",
            "agents": [
                {
                    "name": "OpenCode",
                    "status": "",
                    "message": "",
                    "fetch_error": True,
                    "metadata": {},
                },
            ],
            "num_agents": 1,
            "show_hint": True,
        },
    )
    assert img.size == (250, 122)


def test_render_agent_feed_mixed_and_hint():
    from ui.layouts import render

    # show_hint=False because not all agents failed
    img = render(
        "agent_feed",
        {
            "name": "Agents",
            "agents": [
                {
                    "name": "OpenCode",
                    "status": "working",
                    "message": "coding",
                    "fetch_error": False,
                    "metadata": {},
                },
                {
                    "name": "Cursor",
                    "status": "",
                    "message": "",
                    "fetch_error": True,
                    "metadata": {},
                },
            ],
            "num_agents": 2,
            "show_hint": False,
        },
    )
    assert img.size == (250, 122)


def test_template_unknown_raises():
    from ui.layouts import render

    try:
        render("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_template_custom_canvas():
    from ui.layouts import render
    from ui.canvas import Canvas

    c = Canvas(200, 400)
    img = render("boot", {"name": "Wide"}, canvas=c)
    assert img.size == (200, 400)


# --- Preview ---


def test_preview_render_template():
    import tempfile

    from ui.preview import render_template

    with tempfile.TemporaryDirectory() as td:
        path = render_template("boot", output_dir=td)
        assert os.path.exists(path)


def test_preview_render_all():
    import tempfile

    from ui.preview import render_all

    with tempfile.TemporaryDirectory() as td:
        paths = render_all(output_dir=td)
        assert len(paths) >= 7


# --- UiTemplateScreen integration ---


def test_ui_template_screen_render():
    from core.config import ScreenConfig
    from core.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(name="Boot", type="ui", layout="boot")
    screen = UiTemplateScreen(cfg, "boot")
    img = screen.render(250, 122)
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_ui_template_screen_has_changed():
    from core.config import ScreenConfig
    from core.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(name="Boot", type="ui", layout="boot")
    screen = UiTemplateScreen(cfg, "boot")
    assert screen.has_changed() is True
    screen.render(250, 122)
    assert screen.has_changed() is False


def test_ui_template_screen_poll_interval():
    from core.config import ScreenConfig
    from core.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(
        name="Boot", type="ui", layout="boot", poll_interval=60, display_duration=10
    )
    screen = UiTemplateScreen(cfg, "boot")
    assert screen.poll_interval == 60
    assert screen.display_duration == 10


def test_ui_template_screen_layout_validation():
    from core.config import ScreenConfig
    from core.screens.ui_template import UiTemplateScreen

    # layout is required for type: ui
    cfg = ScreenConfig(name="Boot", type="ui", layout="boot")
    screen = UiTemplateScreen(cfg, "boot")
    assert screen._template_name == "boot"


def test_create_screens_with_ui_layout():
    from core.config import AppConfig, ScreenConfig
    from core.screens import create_screens
    from core.screens.ui_template import UiTemplateScreen

    cfg = AppConfig(screens=[ScreenConfig(name="Boot", type="ui", layout="boot")])
    screens = create_screens(cfg)
    assert len(screens) == 1
    assert isinstance(screens[0], UiTemplateScreen)
    assert screens[0]._template_name == "boot"


def test_create_screens_with_ui_layout_idle():
    from core.config import AppConfig, ScreenConfig
    from core.screens import create_screens
    from core.screens.ui_template import UiTemplateScreen

    cfg = AppConfig(screens=[ScreenConfig(name="Idle", type="ui", layout="idle")])
    screens = create_screens(cfg)
    assert len(screens) == 1
    assert isinstance(screens[0], UiTemplateScreen)
    assert screens[0]._template_name == "idle"


def test_create_screens_mixed_types():
    from core.config import AppConfig, ScreenConfig
    from core.screens import create_screens
    from core.screens.ui_template import UiTemplateScreen
    from core.screens.status_board import StatusBoardScreen

    cfg = AppConfig(
        screens=[
            ScreenConfig(name="Boot", type="ui", layout="boot"),
            ScreenConfig(name="Status", type="status_board"),
            ScreenConfig(name="Idle", type="ui", layout="idle"),
        ]
    )
    screens = create_screens(cfg)
    assert len(screens) == 3
    assert isinstance(screens[0], UiTemplateScreen)
    assert isinstance(screens[1], StatusBoardScreen)
    assert isinstance(screens[2], UiTemplateScreen)


def test_create_screens_unknown_type_raises():
    from core.config import AppConfig, ScreenConfig
    from core.screens import create_screens

    cfg = AppConfig(screens=[ScreenConfig(name="Bad", type="unknown_xyz")])
    try:
        create_screens(cfg)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_render_opencode_working():
    from ui.layouts import render

    img = render(
        "opencode",
        {
            "name": "OpenCode",
            "status": "working",
            "message": "cmd: git commit",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "pending": 1,
            "metadata": {
                "model": "anthropic/claude-3.7-sonnet",
                "tokens_input": 1240,
                "tokens_output": 340,
                "tokens_total": 1580,
                "cost_usd": 0.0042,
                "project": "tamagotchai",
                "message_count": 5,
                "files_modified": 3,
                "tool_name": "bash",
                "session_duration_ms": 245000,
                "lines_added": 45,
                "lines_removed": 12,
                "commits": 2,
            },
            "fetch_error": False,
        },
    )
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_opencode_hint():
    from ui.layouts import render

    img = render(
        "opencode",
        {
            "name": "OpenCode",
            "status": "",
            "message": "",
            "last_heartbeat": "",
            "pending": 0,
            "metadata": {},
            "fetch_error": True,
        },
    )
    assert img.size == (250, 122)
    assert img.mode == "1"


def test_render_opencode_idle():
    from ui.layouts import render

    img = render(
        "opencode",
        {
            "name": "OpenCode",
            "status": "idle",
            "message": "",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "pending": 0,
            "metadata": {"project": "tamagotchai", "message_count": 12},
            "fetch_error": False,
        },
    )
    assert img.size == (250, 122)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
