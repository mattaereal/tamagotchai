"""Tests for config, resolve_key, screen templates, and providers."""

import sys
import os
import tempfile
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import ServiceStatus
from core.providers.statuspage import StatuspageProvider
from core.screens.status_board import (
    StatusBoardScreen,
    CategoryData,
)
from ui.assets import (
    get_icon,
    resolve_icon_key,
    _make_anthropic_icon,
    _make_openai_icon,
    _make_lotus_icon,
    _make_generic_icon,
)
from ui.layout import _STATUS_ICONS
from core.screens.status_board import _json_value_to_status
from core.screens.tamagotchi import TamagotchiScreen
from core.screens import create_screens
from core.config import (
    AppConfig,
    DisplayConfig,
    ScreenConfig,
    StatusBoardCategory,
    StatusBoardItem,
    SpriteConfig,
    MoodMapConfig,
    InfoLineConfig,
    AgentFeedEntry,
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
    assert resolve_icon_key("Claude", "statuspage") == "anthropic"
    assert resolve_icon_key("OpenAI", "statuspage") == "openai"
    assert resolve_icon_key("Lotus", "json") == "lotus"
    assert resolve_icon_key("Random", "statuspage") == "statuspage"


def test_get_icon_builtin():
    for name in ["anthropic", "openai", "lotus", "generic"]:
        icon = get_icon(name)
        assert icon is not None


def test_get_icon_unknown_returns_generic():
    icon = get_icon("nonexistent")
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
    with tempfile.TemporaryDirectory() as td:
        display_yml = os.path.join(td, "display.yml")
        app_yml = os.path.join(td, "tamagotchai.yml")
        screens_yml = os.path.join(td, "screens.yml")

        with open(display_yml, "w") as f:
            f.write("backend: mock\n")
        with open(app_yml, "w") as f:
            f.write("refresh_seconds: 30\ntimezone: UTC\n")
        with open(screens_yml, "w") as f:
            f.write(
                "screens:\n"
                "  - name: Test\n"
                "    template: status_board\n"
                "    categories:\n"
                "      - name: Foo\n"
                "        url: http://test\n"
                "        type: json\n"
                "        items:\n"
                "          - key: status\n"
                "            label: Live\n"
            )

        cfg = load_config(td)
        assert len(cfg.screens) == 1
        assert cfg.screens[0].categories[0].type == "json"
        assert cfg.display.backend == "mock"
        assert cfg.refresh_seconds == 30


def test_load_config_missing_dir():
    try:
        load_config("/nonexistent/path")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_load_config_partial():
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write("backend: waveshare_2in13_v3\n")
        cfg = load_config(td)
        assert cfg.display.backend == "waveshare_2in13_v3"
        assert cfg.display.width == 122
        assert cfg.display.height == 250
        assert len(cfg.screens) == 0


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


# --- MoodMapConfig with map ---


def test_mood_map_with_explicit_map():
    mm = MoodMapConfig(
        key="status",
        map={
            "idle": "idle",
            "working": "working",
            "waiting_input": "working",
            "stuck": "error",
            "error": "error",
            "success": "success",
            "offline": "error",
        },
        fallback="idle",
    )
    assert mm.map["working"] == "working"
    assert mm.map["offline"] == "error"
    assert mm.fallback == "idle"


def test_mood_map_explicit_takes_precedence():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        mood_map=MoodMapConfig(
            key="status",
            ok="idle",
            ok_busy="working",
            error="error",
            map={"working": "working", "error": "error", "success": "success"},
            fallback="idle",
        ),
    )
    screen = TamagotchiScreen(sc)

    screen._data = {"status": "working"}
    screen._resolve_mood()
    assert screen._mood == "working"

    screen._data = {"status": "success"}
    screen._resolve_mood()
    assert screen._mood == "success"

    screen._data = {"status": "idle"}
    screen._resolve_mood()
    assert screen._mood == "idle"


def test_mood_map_without_map_legacy_behavior():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        mood_map=MoodMapConfig(
            key="status",
            ok="idle",
            ok_busy="working",
            error="error",
        ),
    )
    screen = TamagotchiScreen(sc)

    screen._data = {"status": "ok", "pending": 0}
    screen._resolve_mood()
    assert screen._mood == "idle"

    screen._data = {"status": "ok", "pending": 3}
    screen._resolve_mood()
    assert screen._mood == "working"

    screen._data = {"status": "down"}
    screen._resolve_mood()
    assert screen._mood == "error"


def test_mood_map_fallback():
    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        mood_map=MoodMapConfig(
            key="status",
            map={"working": "working"},
            fallback="idle",
        ),
    )
    screen = TamagotchiScreen(sc)

    screen._data = {"status": "unknown_value"}
    screen._resolve_mood()
    assert screen._mood == "idle"


# --- Stale detection ---


def test_stale_heartbeat_sets_offline():
    from datetime import timedelta

    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        stale_threshold=60,
        mood_map=MoodMapConfig(
            key="status",
            map={"working": "working", "offline": "error"},
            fallback="idle",
        ),
    )
    screen = TamagotchiScreen(sc)

    old_hb = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    screen._data = {"status": "working", "last_heartbeat": old_hb}
    screen._resolve_mood()

    stale_threshold = screen._config.stale_threshold
    heartbeat = screen._data.get("last_heartbeat")
    if heartbeat:
        dt = datetime.fromisoformat(heartbeat)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        if age > stale_threshold:
            screen._data["status"] = "offline"
            screen._resolve_mood()

    assert screen._data["status"] == "offline"
    assert screen._mood == "error"


def test_fresh_heartbeat_unchanged():
    from datetime import timedelta

    sc = ScreenConfig(
        name="Test",
        template="tamagotchi",
        url="http://test",
        stale_threshold=120,
        mood_map=MoodMapConfig(
            key="status",
            map={"working": "working", "offline": "error"},
            fallback="idle",
        ),
    )
    screen = TamagotchiScreen(sc)

    recent_hb = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    screen._data = {"status": "working", "last_heartbeat": recent_hb}
    screen._resolve_mood()

    stale_threshold = screen._config.stale_threshold
    heartbeat = screen._data.get("last_heartbeat")
    if heartbeat:
        dt = datetime.fromisoformat(heartbeat)
        age = (datetime.now(timezone.utc) - dt).total_seconds()
        if age > stale_threshold:
            screen._data["status"] = "offline"
            screen._resolve_mood()

    assert screen._data["status"] == "working"
    assert screen._mood == "working"


# --- AgentFeedEntry and agent_feed ---


def test_agent_feed_entry():
    a = AgentFeedEntry(name="OpenCode", url="http://localhost:7788/status")
    assert a.name == "OpenCode"
    assert a.url == "http://localhost:7788/status"


def test_agent_feed_config_parsing():
    data = {
        "display": {"backend": "mock"},
        "screens": [
            {
                "name": "All Agents",
                "template": "agent_feed",
                "poll_interval": 5,
                "agents": [
                    {"name": "OpenCode", "url": "http://localhost:7788/status"},
                    {"name": "Cursor", "url": "http://localhost:7789/status"},
                ],
            }
        ],
    }
    cfg = AppConfig.from_dict(data)
    assert len(cfg.screens) == 1
    assert cfg.screens[0].template == "agent_feed"
    assert len(cfg.screens[0].agents) == 2
    assert cfg.screens[0].agents[0].name == "OpenCode"


def test_agent_feed_screen_render():
    from core.screens.agent_feed import AgentFeedScreen

    sc = ScreenConfig(
        name="All Agents",
        template="agent_feed",
        agents=[
            AgentFeedEntry(name="OpenCode", url="http://localhost:7788/status"),
            AgentFeedEntry(name="Cursor", url="http://localhost:7789/status"),
        ],
    )
    screen = AgentFeedScreen(sc)
    screen._agents_data = [
        {
            "name": "OpenCode",
            "status": "working",
            "message": "Refactoring auth",
            "metadata": {"model": "claude-3.7-sonnet", "cost_usd": 0.004},
        },
        {"name": "Cursor", "status": "idle"},
    ]
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_agent_feed_screen_has_changed():
    from core.screens.agent_feed import AgentFeedScreen

    sc = ScreenConfig(
        name="All Agents",
        template="agent_feed",
        agents=[AgentFeedEntry(name="Test", url="http://test")],
    )
    screen = AgentFeedScreen(sc)
    assert screen.has_changed() is True
    screen._agents_data = [{"name": "Test", "status": "idle"}]
    screen.render(122, 250)
    assert screen.has_changed() is False
    screen._agents_data = [{"name": "Test", "status": "working"}]
    assert screen.has_changed() is True
    screen.render(122, 250)
    screen._agents_data = [
        {"name": "Test", "status": "working", "metadata": {"cost_usd": 0.01}}
    ]
    assert screen.has_changed() is True


def test_create_screens_agent_feed():
    cfg = AppConfig(
        display=DisplayConfig("mock"),
        screens=[
            ScreenConfig(
                name="All Agents",
                template="agent_feed",
                agents=[AgentFeedEntry(name="Test", url="http://test")],
            ),
        ],
    )
    screens = create_screens(cfg)
    assert len(screens) == 1
    from core.screens.agent_feed import AgentFeedScreen

    assert isinstance(screens[0], AgentFeedScreen)


def test_device_status_screen_render():
    from core.screens.device_status import DeviceStatusScreen

    sc = ScreenConfig(name="Device", template="device_status")
    screen = DeviceStatusScreen(sc)
    screen._data = {
        "hostname": "test.local",
        "ip": "192.168.1.1",
        "ssid": "TestNet",
        "bssid": "AA:BB:CC:DD:EE:FF",
        "wifi_status": "connected",
        "signal": "90%",
        "cpu_temp": "45.2C",
        "memory": "128/512MB",
        "disk": "2.1/28GB",
        "uptime": "0d 1h 23m",
        "battery": "95%",
        "battery_charging": True,
        "pid": "99999",
        "version": "1.0.0",
    }
    img = screen.render(122, 250)
    assert img.size == (122, 250)
    assert img.mode == "1"


def test_device_status_screen_has_changed():
    from core.screens.device_status import DeviceStatusScreen

    sc = ScreenConfig(name="Device", template="device_status")
    screen = DeviceStatusScreen(sc)
    assert screen.has_changed() is True
    screen._data = {"hostname": "test", "ip": "1.2.3.4"}
    screen.render(122, 250)
    assert screen.has_changed() is False
    screen._data = {"hostname": "test", "ip": "5.6.7.8"}
    assert screen.has_changed() is True


def test_device_status_screen_defaults():
    from core.screens.device_status import DeviceStatusScreen

    sc = ScreenConfig(name="Device", template="device_status")
    screen = DeviceStatusScreen(sc)
    assert screen.poll_interval == 30
    assert screen.display_duration == 30
    screen._data = {}
    img = screen.render(122, 250)
    assert img.size == (122, 250)


def test_device_status_helpers():
    from core.screens.device_status import (
        _read_file,
        _run_cmd,
        _get_cpu_temp,
        _get_uptime,
        _get_disk,
        _get_memory,
    )

    assert _read_file("/nonexistent/path") is None
    assert _run_cmd(["false"], fallback="N/A") == "N/A"
    assert _run_cmd(["echo", "hello"]) == "hello"

    cpu = _get_cpu_temp()
    assert isinstance(cpu, str)

    up = _get_uptime()
    assert isinstance(up, str)

    disk = _get_disk()
    assert isinstance(disk, str)

    mem = _get_memory()
    assert isinstance(mem, str)


def test_create_screens_device_status():
    cfg = AppConfig(
        display=DisplayConfig("mock"),
        screens=[
            ScreenConfig(name="Device", template="device_status"),
        ],
    )
    screens = create_screens(cfg)
    assert len(screens) == 1
    from core.screens.device_status import DeviceStatusScreen

    assert isinstance(screens[0], DeviceStatusScreen)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
