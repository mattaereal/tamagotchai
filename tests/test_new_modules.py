"""Tests for config, resolve_key, screen templates, and providers."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_health_board.models import ServiceStatus
from ai_health_board.providers.statuspage import StatuspageProvider
from ai_health_board.screens.status_board import (
    StatusBoardScreen,
    CategoryData,
    _STATUS_ICONS,
    _make_anthropic_icon,
    _make_openai_icon,
    _make_lotus_icon,
    _make_generic_icon,
    _get_icon,
    _resolve_icon_key,
    _json_value_to_status,
)
from ai_health_board.screens.tamagotchi import TamagotchiScreen
from ai_health_board.screens import create_screens
from ai_health_board.config import (
    AppConfig,
    DisplayConfig,
    ScreenConfig,
    StatusBoardCategory,
    StatusBoardItem,
    SpriteConfig,
    MoodMapConfig,
    InfoLineConfig,
    load_config,
    resolve_key,
)


# --- resolve_key ---


def test_resolve_key_top_level():
    assert resolve_key({"status": "ok"}, "status") == "ok"


def test_resolve_key_nested():
    assert resolve_key({"a": {"b": 5}}, "a.b") == 5


def test_resolve_key_deep_nesting():
    assert resolve_key({"x": {"y": {"z": 1}}}, "x.y.z") == 1


def test_resolve_key_missing():
    assert resolve_key({"x": 1}, "y.z") is None


def test_resolve_key_default():
    assert resolve_key({"x": 1}, "y", "fallback") == "fallback"


def test_resolve_key_partial_path():
    assert resolve_key({"a": {"b": 1}}, "a.c") is None


# --- ServiceStatus ---


def test_service_status_icons():
    assert ServiceStatus.OK.icon() == "[+]"
    assert ServiceStatus.DEGRADED.icon() == "[!]"
    assert ServiceStatus.DOWN.icon() == "[-]"
    assert ServiceStatus.UNKNOWN.icon() == "[?]"


# --- json_value_to_status ---


def test_json_value_ok():
    for val in ["ok", "up", "operational", "healthy", True, 0]:
        assert _json_value_to_status(val) == ServiceStatus.OK, f"{val} should be OK"


def test_json_value_degraded():
    for val in ["degraded", "warning", "partial", 5, 3.14]:
        assert _json_value_to_status(val) == ServiceStatus.DEGRADED, (
            f"{val} should be DEGRADED"
        )


def test_json_value_down():
    for val in ["down", "error", "offline", "outage", False]:
        assert _json_value_to_status(val) == ServiceStatus.DOWN, f"{val} should be DOWN"


def test_json_value_unknown():
    assert _json_value_to_status("wobble") == ServiceStatus.UNKNOWN
    assert _json_value_to_status(None) == ServiceStatus.UNKNOWN


def test_json_value_dict():
    assert _json_value_to_status({"status": "ok"}) == ServiceStatus.OK
    assert _json_value_to_status({"state": "down"}) == ServiceStatus.DOWN


# --- Status board icons ---


def test_anthropic_icon():
    icon = _make_anthropic_icon()
    assert icon.size == (12, 12)
    assert icon.mode == "1"


def test_openai_icon():
    icon = _make_openai_icon()
    assert icon.size == (12, 12)


def test_lotus_icon():
    icon = _make_lotus_icon()
    assert icon.size == (12, 12)


def test_generic_icon():
    icon = _make_generic_icon()
    assert icon.size == (12, 12)


def test_icon_has_black_pixels():
    for maker in [
        _make_anthropic_icon,
        _make_openai_icon,
        _make_lotus_icon,
        _make_generic_icon,
    ]:
        icon = maker()
        extrema = icon.getextrema()
        assert extrema == (0, 255), f"{maker.__name__} has no black pixels"


def test_resolve_icon_key():
    assert _resolve_icon_key("Claude", "statuspage") == "anthropic"
    assert _resolve_icon_key("OpenAI", "statuspage") == "openai"
    assert _resolve_icon_key("Lotus", "json") == "lotus"
    assert _resolve_icon_key("Random", "statuspage") == "statuspage"


def test_get_icon_builtin():
    for name in ["anthropic", "openai", "lotus", "generic"]:
        icon = _get_icon(name)
        assert icon is not None


def test_get_icon_unknown_returns_generic():
    icon = _get_icon("nonexistent")
    assert icon is not None


def test_status_icons():
    assert _STATUS_ICONS["OK"] == "[+]"
    assert _STATUS_ICONS["DOWN"] == "[-]"
    assert _STATUS_ICONS["DEGRADED"] == "[!]"


# --- StatuspageProvider ---


def test_statuspage_provider_type():
    p = StatuspageProvider(display_name="Test", url="", component_keys=[])
    assert p.provider_type() == "statuspage"


# --- Config data classes ---


def test_info_line_config_key():
    il = InfoLineConfig(label="status", key="status")
    assert il.key == "status"


def test_info_line_config_template():
    il = InfoLineConfig(
        label="PRs", template="+{0} M{1}", keys=["prs_created", "prs_merged"]
    )
    assert il.template == "+{0} M{1}"
    assert il.keys == ["prs_created", "prs_merged"]


def test_mood_map_config_key():
    mm = MoodMapConfig(key="status", ok="idle", ok_busy="working", error="error")
    assert mm.key == "status"


def test_mood_map_config_backward_compat():
    """YAML 'field' should still work as fallback for 'key'."""
    data = {
        "mood_map": {
            "field": "state",
            "ok": "idle",
            "ok_busy": "working",
            "error": "error",
        }
    }
    mm = MoodMapConfig(
        key=data["mood_map"].get("key", data["mood_map"].get("field", "status")),
        ok=data["mood_map"]["ok"],
        ok_busy=data["mood_map"]["ok_busy"],
        error=data["mood_map"]["error"],
    )
    assert mm.key == "state"


def test_sprite_config():
    s = SpriteConfig(
        idle="img/a.png", working="img/b.png", error="img/c.png", success="img/d.png"
    )
    assert s.idle == "img/a.png"


def test_screen_config():
    sc = ScreenConfig(name="AI Health", template="status_board")
    assert sc.template == "status_board"
    assert sc.url == ""


def test_config_from_dict():
    data = {
        "refresh_seconds": 30,
        "display": {"backend": "mock"},
        "screens": [
            {
                "name": "AI Health",
                "template": "status_board",
                "categories": [
                    {
                        "name": "Claude",
                        "url": "http://test",
                        "type": "statuspage",
                        "icon": "anthropic",
                        "items": [{"key": "claude.ai", "label": "AI"}],
                    }
                ],
            },
            {
                "name": "Lotus",
                "template": "tamagotchi",
                "url": "http://test/health",
                "sprites": {
                    "idle": "img/irk_1.png",
                    "working": "img/irk_2.png",
                    "error": "img/irk_3.png",
                    "success": "img/irk_4.png",
                },
                "mood_map": {
                    "key": "status",
                    "ok": "idle",
                    "ok_busy": "working",
                    "error": "error",
                },
                "info_lines": [
                    {"label": "status", "key": "status"},
                    {
                        "label": "PRs",
                        "template": "+{0} M{1}",
                        "keys": ["prs_created", "prs_merged"],
                    },
                ],
            },
        ],
    }
    cfg = AppConfig.from_dict(data)
    assert len(cfg.screens) == 2

    s0 = cfg.screens[0]
    assert s0.template == "status_board"
    assert s0.categories[0].items[0].label == "AI"

    s1 = cfg.screens[1]
    assert s1.template == "tamagotchi"
    assert s1.sprites.idle == "img/irk_1.png"
    assert s1.mood_map.key == "status"
    assert s1.info_lines[1].keys == ["prs_created", "prs_merged"]


def test_config_info_line_backward_compat():
    """YAML 'field' should map to 'key', 'fields' to 'keys'."""
    data = {
        "display": {"backend": "mock"},
        "screens": [
            {
                "name": "Test",
                "template": "tamagotchi",
                "url": "http://test",
                "info_lines": [
                    {"label": "status", "field": "status"},
                    {"label": "PRs", "template": "+{0}", "fields": ["prs_created"]},
                ],
            }
        ],
    }
    cfg = AppConfig.from_dict(data)
    il0 = cfg.screens[0].info_lines[0]
    il1 = cfg.screens[0].info_lines[1]
    assert il0.key == "status"
    assert il1.keys == ["prs_created"]


def test_load_config_yaml():
    yaml_content = """
refresh_seconds: 30
display:
  backend: mock
screens:
  - name: Test
    template: status_board
    categories:
      - name: Foo
        url: http://test
        type: json
        items:
          - key: status
            label: Live
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        fname = f.name
    try:
        cfg = load_config(fname)
        assert len(cfg.screens) == 1
        assert cfg.screens[0].categories[0].type == "json"
    finally:
        os.unlink(fname)


# --- StatusBoardScreen ---


def test_status_board_render_empty():
    sc = ScreenConfig(name="Test", template="status_board")
    screen = StatusBoardScreen(sc)
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_status_board_has_changed_initial():
    sc = ScreenConfig(name="Test", template="status_board")
    screen = StatusBoardScreen(sc)
    assert screen.has_changed() is True


def test_status_board_has_changed_after_render():
    sc = ScreenConfig(name="Test", template="status_board")
    screen = StatusBoardScreen(sc)
    screen.render(122, 250)
    assert screen.has_changed() is False


def test_status_board_render_with_data():
    sc = ScreenConfig(name="AI Health", template="status_board")
    screen = StatusBoardScreen(sc)
    screen._categories = [
        CategoryData(
            "Claude", "anthropic", {"AI": ServiceStatus.OK, "Code": ServiceStatus.OK}
        ),
        CategoryData("OpenAI", "openai", {"App": ServiceStatus.DEGRADED}),
    ]
    screen._last_refresh = None
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_status_board_data_change():
    sc = ScreenConfig(name="Test", template="status_board")
    screen = StatusBoardScreen(sc)
    screen._categories = [CategoryData("Test", "generic", {"Foo": ServiceStatus.OK})]
    screen._last_refresh = None
    screen.render(122, 250)
    assert screen.has_changed() is False
    screen._categories[0].items["Foo"] = ServiceStatus.DOWN
    assert screen.has_changed() is True


# --- TamagotchiScreen ---


def test_tamagotchi_render_empty():
    sc = ScreenConfig(name="Test", template="tamagotchi", url="http://test")
    screen = TamagotchiScreen(sc)
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_tamagotchi_has_changed_initial():
    sc = ScreenConfig(name="Test", template="tamagotchi", url="http://test")
    screen = TamagotchiScreen(sc)
    assert screen.has_changed() is True


def test_tamagotchi_has_changed_after_render():
    sc = ScreenConfig(name="Test", template="tamagotchi", url="http://test")
    screen = TamagotchiScreen(sc)
    screen.render(122, 250)
    assert screen.has_changed() is False


def test_tamagotchi_mood_resolve():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        mood_map=MoodMapConfig(
            key="status", ok="idle", ok_busy="working", error="error"
        ),
    )
    screen = TamagotchiScreen(sc)

    screen._data = {"status": "ok", "pending": 0}
    screen._resolve_mood()
    assert screen._mood == "idle"

    screen._data = {"status": "ok", "pending": 3}
    screen._resolve_mood()
    assert screen._mood == "working"

    screen._data = {"status": "down", "pending": 0}
    screen._resolve_mood()
    assert screen._mood == "error"


def test_tamagotchi_mood_resolve_nested_key():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        mood_map=MoodMapConfig(
            key="health.status", ok="idle", ok_busy="working", error="error"
        ),
    )
    screen = TamagotchiScreen(sc)
    screen._data = {"health": {"status": "ok"}, "pending": 0}
    screen._resolve_mood()
    assert screen._mood == "idle"


def test_tamagotchi_info_line_simple_key():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        info_lines=[InfoLineConfig(label="status", key="status")],
    )
    screen = TamagotchiScreen(sc)
    screen._data = {"status": "ok"}
    val = screen._format_info_line(sc.info_lines[0])
    assert val == "ok"


def test_tamagotchi_info_line_nested_key():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        info_lines=[InfoLineConfig(label="health", key="data.health")],
    )
    screen = TamagotchiScreen(sc)
    screen._data = {"data": {"health": "ok"}}
    val = screen._format_info_line(sc.info_lines[0])
    assert val == "ok"


def test_tamagotchi_info_line_template_positional():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        info_lines=[
            InfoLineConfig(
                label="PRs", template="+{0} M{1}", keys=["prs_created", "prs_merged"]
            )
        ],
    )
    screen = TamagotchiScreen(sc)
    screen._data = {"prs_created": 12, "prs_merged": 8}
    val = screen._format_info_line(sc.info_lines[0])
    assert val == "+12 M8"


def test_tamagotchi_info_line_template_nested_keys():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        info_lines=[
            InfoLineConfig(label="PRs", template="+{0}", keys=["activity.prs_created"])
        ],
    )
    screen = TamagotchiScreen(sc)
    screen._data = {"activity": {"prs_created": 5}}
    val = screen._format_info_line(sc.info_lines[0])
    assert val == "+5"


def test_tamagotchi_data_change():
    sc = ScreenConfig(name="Test", template="tamagotchi", url="http://test")
    screen = TamagotchiScreen(sc)
    screen._data = {"status": "ok"}
    screen._resolve_mood()
    screen.render(122, 250)
    assert screen.has_changed() is False
    screen._data = {"status": "down"}
    screen._resolve_mood()
    assert screen.has_changed() is True


def test_tamagotchi_with_sprites():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        sprites=SpriteConfig(
            idle="img/irk_1.png",
            working="img/irk_2.png",
            error="img/irk_3.png",
            success="img/irk_4.png",
        ),
    )
    screen = TamagotchiScreen(sc)
    assert len(screen._sprites) == 4
    img = screen.render(122, 250)
    assert img.size == (122, 250)


# --- create_screens factory ---


def test_create_screens_default():
    cfg = AppConfig(display=DisplayConfig("mock"))
    screens = create_screens(cfg)
    assert len(screens) == 1
    assert isinstance(screens[0], StatusBoardScreen)


def test_create_screens_from_config():
    cfg = AppConfig(
        display=DisplayConfig("mock"),
        screens=[
            ScreenConfig(name="AI Health", template="status_board"),
            ScreenConfig(name="Lotus", template="tamagotchi", url="http://test"),
        ],
    )
    screens = create_screens(cfg)
    assert len(screens) == 2
    assert isinstance(screens[0], StatusBoardScreen)
    assert isinstance(screens[1], TamagotchiScreen)


# --- Demo mock injection ---


def test_mock_status_board_injection():
    sc = ScreenConfig(name="AI Health", template="status_board")
    screen = StatusBoardScreen(sc)
    from app import _inject_mock_status_board

    _inject_mock_status_board(screen)
    assert len(screen._categories) == 3
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_mock_tamagotchi_injection():
    sc = ScreenConfig(name="Lotus", template="tamagotchi", url="http://test")
    screen = TamagotchiScreen(sc)
    from app import _inject_mock_tamagotchi

    _inject_mock_tamagotchi(screen)
    assert screen._data.get("status") == "ok"
    img = screen.render(122, 250)
    assert img.size == (122, 250)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
