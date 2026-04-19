"""Tests for ui.templates and the screen-cycling integration."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image


# --- Template Registry ---


def test_template_registry():
    from ui.templates import names

    n = names()
    assert "boot" in n
    assert "setup" in n
    assert "status_dashboard" in n
    assert "detail" in n
    assert "message" in n
    assert "idle" in n
    assert "error" in n


def test_render_boot():
    from ui.templates import render

    img = render("boot", {"name": "Test", "version": "2.0"})
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_setup():
    from ui.templates import render

    img = render("setup")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_status_dashboard():
    from ui.templates import render

    img = render("status_dashboard")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_status_dashboard_with_categories():
    from ui.templates import render

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
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_status_dashboard_overflow():
    from ui.templates import render

    categories = []
    for i in range(20):
        categories.append(
            {
                "name": f"Cat{i}",
                "items": [{"label": f"item{j}", "status": "OK"} for j in range(5)],
            }
        )
    img = render("status_dashboard", {"categories": categories})
    assert img.size == (122, 250)


def test_render_detail():
    from ui.templates import render

    img = render("detail")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_detail_with_metrics():
    from ui.templates import render

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
    assert img.size == (122, 250)


def test_render_message():
    from ui.templates import render

    img = render("message")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_message_string_body():
    from ui.templates import render

    img = render("message", {"title": "WARN", "body": "Single line"})
    assert img.size == (122, 250)


def test_render_message_no_title():
    from ui.templates import render

    img = render("message", {"body": ["Line 1", "Line 2"]})
    assert img.size == (122, 250)


def test_render_idle():
    from ui.templates import render

    img = render("idle")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_idle_with_sprite():
    from ui.templates import render

    sprite = Image.new("1", (90, 90), 255)
    img = render("idle", {"name": "Bot", "mood": "working", "sprite": sprite})
    assert img.size == (122, 250)


def test_render_idle_moods():
    from ui.templates import render

    for mood in ("idle", "working", "error"):
        img = render("idle", {"mood": mood})
        assert img.size == (122, 250)


def test_render_error():
    from ui.templates import render

    img = render("error")
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_render_error_with_detail():
    from ui.templates import render

    img = render(
        "error",
        {
            "message": "Timeout",
            "detail": "Connection to upstream server failed after 10 seconds",
            "last_ok": "14:30",
        },
    )
    assert img.size == (122, 250)


def test_template_unknown_raises():
    from ui.templates import render

    try:
        render("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_template_custom_canvas():
    from ui.templates import render
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
    from ai_health_board.config import ScreenConfig
    from ai_health_board.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(name="Boot", template="ui:boot")
    screen = UiTemplateScreen(cfg, "boot")
    img = screen.render(122, 250)
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_ui_template_screen_has_changed():
    from ai_health_board.config import ScreenConfig
    from ai_health_board.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(name="Boot", template="ui:boot")
    screen = UiTemplateScreen(cfg, "boot")
    assert screen.has_changed() is True
    screen.render(122, 250)
    assert screen.has_changed() is False


def test_ui_template_screen_poll_interval():
    from ai_health_board.config import ScreenConfig
    from ai_health_board.screens.ui_template import UiTemplateScreen

    cfg = ScreenConfig(
        name="Boot", template="ui:boot", poll_interval=60, display_duration=10
    )
    screen = UiTemplateScreen(cfg, "boot")
    assert screen.poll_interval == 60
    assert screen.display_duration == 10


def test_ui_template_screen_is_ui_template():
    from ai_health_board.screens.ui_template import UiTemplateScreen

    assert UiTemplateScreen.is_ui_template("ui:boot") is True
    assert UiTemplateScreen.is_ui_template("ui:error") is True
    assert UiTemplateScreen.is_ui_template("boot") is True
    assert UiTemplateScreen.is_ui_template("idle") is True
    assert UiTemplateScreen.is_ui_template("status_board") is False
    assert UiTemplateScreen.is_ui_template("tamagotchi") is False
    assert UiTemplateScreen.is_ui_template("nonexistent_xyz") is False


def test_ui_template_screen_strip_prefix():
    from ai_health_board.screens.ui_template import UiTemplateScreen

    assert UiTemplateScreen.strip_prefix("ui:boot") == "boot"
    assert UiTemplateScreen.strip_prefix("ui:error") == "error"
    assert UiTemplateScreen.strip_prefix("boot") == "boot"


def test_create_screens_with_ui_template():
    from ai_health_board.config import AppConfig, ScreenConfig
    from ai_health_board.screens import create_screens
    from ai_health_board.screens.ui_template import UiTemplateScreen

    cfg = AppConfig(screens=[ScreenConfig(name="Boot", template="ui:boot")])
    screens = create_screens(cfg)
    assert len(screens) == 1
    assert isinstance(screens[0], UiTemplateScreen)
    assert screens[0]._template_name == "boot"


def test_create_screens_with_bare_ui_template():
    from ai_health_board.config import AppConfig, ScreenConfig
    from ai_health_board.screens import create_screens
    from ai_health_board.screens.ui_template import UiTemplateScreen

    cfg = AppConfig(screens=[ScreenConfig(name="Idle", template="idle")])
    screens = create_screens(cfg)
    assert len(screens) == 1
    assert isinstance(screens[0], UiTemplateScreen)
    assert screens[0]._template_name == "idle"


def test_create_screens_mixed_templates():
    from ai_health_board.config import AppConfig, ScreenConfig
    from ai_health_board.screens import create_screens
    from ai_health_board.screens.ui_template import UiTemplateScreen
    from ai_health_board.screens.status_board import StatusBoardScreen

    cfg = AppConfig(
        screens=[
            ScreenConfig(name="Boot", template="ui:boot"),
            ScreenConfig(name="Status", template="status_board"),
            ScreenConfig(name="Idle", template="idle"),
        ]
    )
    screens = create_screens(cfg)
    assert len(screens) == 3
    assert isinstance(screens[0], UiTemplateScreen)
    assert isinstance(screens[1], StatusBoardScreen)
    assert isinstance(screens[2], UiTemplateScreen)


def test_create_screens_unknown_template_raises():
    from ai_health_board.config import AppConfig, ScreenConfig
    from ai_health_board.screens import create_screens

    cfg = AppConfig(screens=[ScreenConfig(name="Bad", template="unknown_xyz")])
    try:
        create_screens(cfg)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
