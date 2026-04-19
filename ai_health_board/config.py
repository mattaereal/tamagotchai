"""Configuration loading and validation.

Config is split across three YAML files in a config directory:
  - display.yml      Hardware/display settings
  - tamagotchai.yml  App-level settings (refresh, timezone)
  - screens.yml      Screen definitions (status boards, tamagotchis, etc.)

Loading merges all three. Each file is optional -- defaults are used
for any missing file.
"""

import logging
import os
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


DISPLAY_CONFIG_FILE = "display.yml"
APP_CONFIG_FILE = "tamagotchai.yml"
SCREENS_CONFIG_FILE = "screens.yml"

DISPLAY_PROFILES = {
    "mock": {
        "width": 122,
        "height": 250,
        "description": "Mock PNG output (development)",
    },
    "waveshare_2in13_v1": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" V1 (B/W, 122x250)',
    },
    "waveshare_2in13_v2": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" V2 (B/W, 122x250)',
    },
    "waveshare_2in13_v3": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" V3 (B/W, 122x250)',
    },
    "waveshare_2in13_v4": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" V4 (B/W, 122x250)',
    },
    "waveshare_2in13bc": {
        "width": 104,
        "height": 212,
        "description": 'Waveshare 2.13" BC (B/W/R, 104x212, no partial)',
    },
    "waveshare_2in13b_v3": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" B V3 (B/W/R, 122x250, no partial)',
    },
    "waveshare_2in13b_v4": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" B V4 (B/W/R, 122x250, no partial)',
    },
    "waveshare_2in13d": {
        "width": 104,
        "height": 212,
        "description": 'Waveshare 2.13" D (B/W, 104x212, flexible)',
    },
    "waveshare_2in13g": {
        "width": 122,
        "height": 250,
        "description": 'Waveshare 2.13" G (4-color, 122x250, no partial)',
    },
}


def resolve_key(data: dict, key_path: str, default: Any = None) -> Any:
    """Resolve a dot-notation key path against a dict.

    Examples:
        resolve_key({"status": "ok"}, "status") -> "ok"
        resolve_key({"a": {"b": 5}}, "a.b") -> 5
        resolve_key({"x": 1}, "y.z") -> None
    """
    keys = key_path.split(".")
    current = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current


def _load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Config file {path} root must be a mapping (dictionary)")
    return raw


@dataclass
class DisplayConfig:
    backend: str
    width: int = 122
    height: int = 250
    rotation: int = 0
    full_refresh_every_n_updates: int = 50


@dataclass
class ProviderConfig:
    """Internal provider config used to instantiate providers from category data."""

    name: str
    type: str
    url: str
    components: List[str] = dataclass_field(default_factory=list)


@dataclass
class StatusBoardItem:
    key: str
    label: str


@dataclass
class StatusBoardCategory:
    name: str
    url: str
    type: str
    icon: str = "generic"
    items: List[StatusBoardItem] = dataclass_field(default_factory=list)


@dataclass
class MoodMapConfig:
    key: str = "status"
    ok: str = "idle"
    ok_busy: str = "working"
    error: str = "error"


@dataclass
class InfoLineConfig:
    label: str
    key: str = ""
    template: str = ""
    keys: List[str] = dataclass_field(default_factory=list)
    max_length: int = 20


@dataclass
class SpriteConfig:
    idle: str = ""
    working: str = ""
    error: str = ""
    success: str = ""


@dataclass
class ScreenConfig:
    name: str
    template: str
    poll_interval: int = 30
    display_duration: int = 30
    categories: List[StatusBoardCategory] = dataclass_field(default_factory=list)
    url: str = ""
    sprites: Optional[SpriteConfig] = None
    mood_map: Optional[MoodMapConfig] = None
    info_lines: List[InfoLineConfig] = dataclass_field(default_factory=list)


@dataclass
class AppConfig:
    refresh_seconds: int = 300
    timezone: str = "UTC"
    display: DisplayConfig = dataclass_field(
        default_factory=lambda: DisplayConfig("mock")
    )
    screens: List[ScreenConfig] = dataclass_field(default_factory=list)
    config_dir: str = "config"

    @staticmethod
    def from_dict(data: Dict[str, Any], config_dir: str = "config") -> "AppConfig":
        display_raw = data.get("display", {})
        backend = display_raw.get("backend", "mock")

        if backend in DISPLAY_PROFILES and "width" not in display_raw:
            display_raw.setdefault("width", DISPLAY_PROFILES[backend]["width"])
            display_raw.setdefault("height", DISPLAY_PROFILES[backend]["height"])

        display = DisplayConfig(
            backend=backend,
            width=display_raw.get("width", 122),
            height=display_raw.get("height", 250),
            rotation=display_raw.get("rotation", 0),
            full_refresh_every_n_updates=display_raw.get(
                "full_refresh_every_n_updates", 50
            ),
        )

        screens: List[ScreenConfig] = []
        for s_raw in data.get("screens", []):
            categories: List[StatusBoardCategory] = []
            for cat_raw in s_raw.get("categories", []):
                items: List[StatusBoardItem] = []
                for item_raw in cat_raw.get("items", []):
                    if isinstance(item_raw, dict):
                        items.append(
                            StatusBoardItem(
                                key=item_raw.get("key", ""),
                                label=item_raw.get("label", item_raw.get("key", "")),
                            )
                        )
                    elif isinstance(item_raw, str):
                        items.append(StatusBoardItem(key=item_raw, label=item_raw))

                cat_url = cat_raw.get("url", "")
                if cat_url and not cat_url.startswith(("http://", "https://")):
                    cat_url = os.path.join(config_dir, cat_url)

                categories.append(
                    StatusBoardCategory(
                        name=cat_raw.get("name", ""),
                        url=cat_url,
                        type=cat_raw.get("type", "statuspage"),
                        icon=cat_raw.get("icon", "generic"),
                        items=items,
                    )
                )

            sprites = None
            sprites_raw = s_raw.get("sprites")
            if sprites_raw and isinstance(sprites_raw, dict):
                sprites = SpriteConfig(
                    idle=sprites_raw.get("idle", ""),
                    working=sprites_raw.get("working", ""),
                    error=sprites_raw.get("error", ""),
                    success=sprites_raw.get("success", ""),
                )

            mood_map = None
            mood_raw = s_raw.get("mood_map")
            if mood_raw and isinstance(mood_raw, dict):
                mood_map = MoodMapConfig(
                    key=mood_raw.get("key", mood_raw.get("field", "status")),
                    ok=mood_raw.get("ok", "idle"),
                    ok_busy=mood_raw.get("ok_busy", "working"),
                    error=mood_raw.get("error", "error"),
                )

            info_lines: List[InfoLineConfig] = []
            for il_raw in s_raw.get("info_lines", []):
                info_lines.append(
                    InfoLineConfig(
                        label=il_raw.get("label", ""),
                        key=il_raw.get("key", il_raw.get("field", "")),
                        template=il_raw.get("template", ""),
                        keys=il_raw.get("keys", il_raw.get("fields", [])),
                        max_length=il_raw.get("max_length", 20),
                    )
                )

            screens.append(
                ScreenConfig(
                    name=s_raw.get("name", ""),
                    template=s_raw.get("template", "status_board"),
                    poll_interval=s_raw.get("poll_interval", 30),
                    display_duration=s_raw.get("display_duration", 30),
                    categories=categories,
                    url=s_raw.get("url", ""),
                    sprites=sprites,
                    mood_map=mood_map,
                    info_lines=info_lines,
                )
            )

        return AppConfig(
            refresh_seconds=data.get("refresh_seconds", 300),
            timezone=data.get("timezone", "UTC"),
            display=display,
            screens=screens,
            config_dir=config_dir,
        )


def load_config(config_dir: str) -> AppConfig:
    """Load config from a directory containing display.yml, tamagotchai.yml, screens.yml."""
    if not os.path.isdir(config_dir):
        raise FileNotFoundError(f"Config directory not found: {config_dir}")

    display_raw = _load_yaml(os.path.join(config_dir, DISPLAY_CONFIG_FILE))
    app_raw = _load_yaml(os.path.join(config_dir, APP_CONFIG_FILE))
    screens_raw = _load_yaml(os.path.join(config_dir, SCREENS_CONFIG_FILE))

    merged: Dict[str, Any] = {}
    merged.update(app_raw)
    if display_raw:
        merged["display"] = display_raw
    if screens_raw:
        merged["screens"] = screens_raw.get("screens", [])

    config = AppConfig.from_dict(merged, config_dir=config_dir)

    if config.refresh_seconds <= 0:
        raise ValueError("refresh_seconds must be positive")
    if not config.screens:
        logger.warning("No screens configured -- app will run but show nothing.")

    logger.info(
        f"Loaded config from {config_dir} with {len(config.screens)} screen(s), "
        f"backend={config.display.backend}"
    )
    return config
