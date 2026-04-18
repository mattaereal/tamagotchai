"""Configuration loading and validation."""

import logging
import os
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


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

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AppConfig":
        display_raw = data.get("display", {})
        display = DisplayConfig(
            backend=display_raw.get("backend", "mock"),
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
                categories.append(
                    StatusBoardCategory(
                        name=cat_raw.get("name", ""),
                        url=cat_raw.get("url", ""),
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
        )


def load_config(path: str) -> AppConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping (dictionary)")

    config = AppConfig.from_dict(raw)

    if config.refresh_seconds <= 0:
        raise ValueError("refresh_seconds must be positive")
    if not config.screens:
        logger.warning("No screens configured -- app will run but show nothing.")

    logger.info(f"Loaded config with {len(config.screens)} screen(s)")
    return config
