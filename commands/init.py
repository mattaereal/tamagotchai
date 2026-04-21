"""Interactive setup wizard for tamagotchai.

Generates the three config files in a config directory:
  - display.yml       Hardware/display settings
  - tamagotchai.yml   App-level settings
  - screens.yml       Screen definitions

Usage:
    python app.py init
    python app.py init --config config
    python app.py init --force            # overwrite existing files
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

import yaml

from core.config import DISPLAY_PROFILES


DISPLAY_CHOICES = [
    ("mock", "Mock PNG output (development)"),
    ("waveshare_2in13_v1", 'Waveshare 2.13" V1 (B/W, 122x250)'),
    ("waveshare_2in13_v2", 'Waveshare 2.13" V2 (B/W, 122x250)'),
    ("waveshare_2in13_v3", 'Waveshare 2.13" V3 (B/W, 122x250)'),
    ("waveshare_2in13_v4", 'Waveshare 2.13" V4 (B/W, 122x250, fast refresh)'),
    ("waveshare_2in13bc", 'Waveshare 2.13" BC (B/W/R, 104x212, no partial)'),
    ("waveshare_2in13b_v3", 'Waveshare 2.13" B V3 (B/W/R, 122x250, no partial)'),
    ("waveshare_2in13b_v4", 'Waveshare 2.13" B V4 (B/W/R, 122x250, no partial)'),
    ("waveshare_2in13d", 'Waveshare 2.13" D (B/W, 104x212, flexible)'),
    ("waveshare_2in13g", 'Waveshare 2.13" G (4-color, 122x250, no partial)'),
]

TYPE_CHOICES = [
    ("status_board", "Category/bullet status display"),
    ("tamagotchi", "Character-based agent monitor"),
    ("agent_feed", "Multi-agent compact list"),
]

BUILTIN_ICONS = ["anthropic", "openai", "lotus", "generic"]


def _prompt(prompt: str, default: str = "") -> str:
    if default:
        raw = input(f"? {prompt} [{default}]: ").strip()
        return raw if raw else default
    raw = input(f"? {prompt}: ").strip()
    return raw


def _choose(prompt: str, choices: List[tuple], default_idx: int = 0) -> str:
    print(f"\n? {prompt}")
    for i, (key, desc) in enumerate(choices):
        marker = " <-" if i == default_idx else ""
        print(f"  {i + 1}. {desc}{marker}")
    raw = input(f"  Choose [1-{len(choices)}] (default {default_idx + 1}): ").strip()
    if not raw:
        return choices[default_idx][0]
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(choices):
            return choices[idx][0]
    except ValueError:
        pass
    for key, desc in choices:
        if key == raw.lower():
            return key
    print(f"  [!] Invalid choice, using default: {choices[default_idx][1]}")
    return choices[default_idx][0]


def _confirm(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"? {prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _configure_display() -> Dict[str, Any]:
    print("\n--- Display Configuration ---")
    backend = _choose(
        "Which e-paper display are you using?", DISPLAY_CHOICES, default_idx=4
    )
    profile = DISPLAY_PROFILES.get(backend, {})
    config: Dict[str, Any] = {"backend": backend}
    if "width" in profile:
        config["width"] = profile["width"]
    if "height" in profile:
        config["height"] = profile["height"]

    rotation = _prompt("Rotation (0, 90, 180, 270)", "0")
    config["rotation"] = int(rotation)

    if backend != "mock":
        config["full_refresh_every_n_updates"] = int(
            _prompt("Full refresh every N updates (clears ghosting)", "50")
        )

    return config


def _configure_app() -> Dict[str, Any]:
    print("\n--- Application Settings ---")
    config: Dict[str, Any] = {}
    config["refresh_seconds"] = int(_prompt("Refresh interval (seconds)", "30"))
    config["timezone"] = _prompt(
        "Timezone (e.g. UTC, US/Eastern, Europe/London)", "UTC"
    )
    return config


def _configure_category() -> Dict[str, Any]:
    cat: Dict[str, Any] = {}
    cat["name"] = _prompt("Category name")
    cat["url"] = _prompt("URL")
    cat["type"] = _prompt("Type (statuspage/json)", "statuspage")

    icon_input = _prompt(
        f"Icon ({'/'.join(BUILTIN_ICONS)}/path/to/12x12.png)", "generic"
    )
    cat["icon"] = icon_input

    items = []
    print("  Items (key=label pairs, blank line to finish):")
    while True:
        item_input = _prompt("  Item (e.g. claude.ai=AI)", "")
        if not item_input:
            break
        if "=" in item_input:
            key, label = item_input.split("=", 1)
            items.append({"key": key.strip(), "label": label.strip()})
        else:
            items.append({"key": item_input.strip(), "label": item_input.strip()})
    cat["items"] = items
    return cat


def _configure_status_board() -> Dict[str, Any]:
    screen: Dict[str, Any] = {}
    screen["type"] = "status_board"
    screen["poll_interval"] = int(_prompt("Poll interval (seconds)", "30"))
    screen["display_duration"] = int(_prompt("Display duration (seconds)", "30"))

    categories = []
    print("\n  Categories (blank name to finish):")
    while True:
        name = _prompt("  Category name", "")
        if not name:
            break
        cat = _configure_category()
        cat["name"] = name
        categories.append(cat)
    screen["categories"] = categories
    return screen


def _configure_tamagotchi() -> Dict[str, Any]:
    screen: Dict[str, Any] = {}
    screen["type"] = "tamagotchi"
    screen["url"] = _prompt("JSON endpoint URL")
    screen["poll_interval"] = int(_prompt("Poll interval (seconds)", "5"))
    screen["display_duration"] = int(_prompt("Display duration (seconds)", "15"))

    sprites: Dict[str, str] = {}
    print("\n  Sprite images (leave blank for built-in fallback face):")
    for mood in ("idle", "working", "error", "success"):
        path = _prompt(f"  {mood} sprite path", "")
        if path:
            sprites[mood] = path
    if sprites:
        screen["sprites"] = sprites

    mood_key = _prompt("Mood field (JSON key that drives sprite selection)", "status")
    screen["mood_map"] = {
        "key": mood_key,
        "ok": _prompt("Mood when OK", "idle"),
        "ok_busy": _prompt("Mood when OK but busy", "working"),
        "error": _prompt("Mood on error", "error"),
    }

    info_lines = []
    print("\n  Info lines (blank label to finish):")
    while True:
        label = _prompt("  Line label", "")
        if not label:
            break
        il: Dict[str, Any] = {"label": label}
        key = _prompt("  Key (dot-notation)", "")
        if key:
            il["key"] = key
        else:
            tmpl = _prompt("  Template (e.g. '+{0} M{1}')", "")
            keys_str = _prompt("  Keys (comma-separated)", "")
            if tmpl:
                il["template"] = tmpl
            if keys_str:
                il["keys"] = [k.strip() for k in keys_str.split(",")]
        il["max_length"] = int(_prompt("  Max length", "20"))
        info_lines.append(il)
    screen["info_lines"] = info_lines
    return screen


def _configure_agent_feed() -> Dict[str, Any]:
    screen: Dict[str, Any] = {}
    screen["type"] = "agent_feed"
    screen["poll_interval"] = int(_prompt("Poll interval (seconds)", "5"))
    screen["display_duration"] = int(_prompt("Display duration (seconds)", "30"))
    screen["stale_threshold"] = int(_prompt("Stale threshold (seconds)", "120"))

    agents = []
    print("\n  Agents (blank name to finish):")
    while True:
        name = _prompt("  Agent name", "")
        if not name:
            break
        url = _prompt("  Status URL", "")
        agents.append({"name": name, "url": url})
    screen["agents"] = agents
    return screen


def _configure_screens() -> List[Dict[str, Any]]:
    print("\n--- Screen Configuration ---")
    screens = []
    num = int(_prompt("How many screens?", "2"))

    for i in range(num):
        print(f"\n--- Screen {i + 1} ---")
        name = _prompt("Screen name", f"Screen {i + 1}")
        type_choice = _choose("Type", TYPE_CHOICES, default_idx=0)

        if type_choice == "status_board":
            screen = _configure_status_board()
        elif type_choice == "tamagotchi":
            screen = _configure_tamagotchi()
        elif type_choice == "agent_feed":
            screen = _configure_agent_feed()
        else:
            screen = {"type": type_choice}

        screen["name"] = name
        screens.append(screen)

    return screens


def run_init(config_dir: str = "config", force: bool = False) -> None:
    """Run the interactive setup wizard."""
    print("=" * 50)
    print("  TAMAGOTCHAI SETUP WIZARD")
    print("=" * 50)

    display_path = os.path.join(config_dir, "display.yml")
    app_path = os.path.join(config_dir, "tamagotchai.yml")
    screens_path = os.path.join(config_dir, "screens.yml")

    existing = [p for p in (display_path, app_path, screens_path) if os.path.exists(p)]
    if existing and not force:
        print(f"\n[!] Config files already exist:")
        for p in existing:
            print(f"    {p}")
        if not _confirm("Overwrite?", default=False):
            print("Aborted. Use --force to overwrite without asking.")
            return

    display_config = _configure_display()
    app_config = _configure_app()
    screens_list = _configure_screens()

    print("\n--- Review ---")
    print(f"\nDisplay:")
    print(f"  backend: {display_config['backend']}")
    print(
        f"  size: {display_config.get('width', '?')}x{display_config.get('height', '?')}"
    )
    print(f"\nApp:")
    print(f"  refresh: {app_config['refresh_seconds']}s")
    print(f"  timezone: {app_config['timezone']}")
    print(f"\nScreens: {len(screens_list)}")
    for s in screens_list:
        print(f"  - {s.get('name', '?')} ({s.get('type', '?')})")

    if not _confirm("\nWrite config files?", default=True):
        print("Aborted.")
        return

    os.makedirs(config_dir, exist_ok=True)

    with open(display_path, "w") as f:
        yaml.dump(display_config, f, default_flow_style=False, sort_keys=False)
    print(f"  {display_path}")

    with open(app_path, "w") as f:
        yaml.dump(app_config, f, default_flow_style=False, sort_keys=False)
    print(f"  {app_path}")

    screens_config = {"screens": screens_list}
    with open(screens_path, "w") as f:
        yaml.dump(screens_config, f, default_flow_style=False, sort_keys=False)
    print(f"  {screens_path}")

    print("\nSetup complete! Try: python app.py demo")
