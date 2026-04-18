"""Configuration loading and validation."""
import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

import yaml

from .models import ProviderStatus, ServiceStatus

logger = logging.getLogger(__name__)


@dataclass
class DisplayConfig:
    backend: str
    width: int = 250
    height: int = 122
    rotation: int = 90
    full_refresh_every_n_updates: int = 6


@dataclass
class ProviderConfig:
    name: str
    type: str
    url: str
    components: List[str]


@dataclass
class AppConfig:
    refresh_seconds: int = 300
    timezone: str = "UTC"
    display: DisplayConfig = field(default_factory=lambda: DisplayConfig("mock"))
    providers: List[ProviderConfig] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AppConfig":
        """Load AppConfig from a dictionary (typically YAML)."""
        display_raw = data.get("display", {})
        display = DisplayConfig(
            backend=display_raw.get("backend", "mock"),
            width=display_raw.get("width", 250),
            height=display_raw.get("height", 122),
            rotation=display_raw.get("rotation", 90),
            full_refresh_every_n_updates=display_raw.get(
                "full_refresh_every_n_updates", 6
            ),
        )

        providers: List[ProviderConfig] = []
        for p_raw in data.get("providers", []):
            providers.append(
                ProviderConfig(
                    name=p_raw["name"],
                    type=p_raw["type"],
                    url=p_raw["url"],
                    components=p_raw.get("components", []),
                )
            )

        return AppConfig(
            refresh_seconds=data.get("refresh_seconds", 300),
            timezone=data.get("timezone", "UTC"),
            display=display,
            providers=providers,
        )


def load_config(path: str) -> AppConfig:
    """Load and validate configuration from a YAML file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping (dictionary)")

    config = AppConfig.from_dict(raw)

    # Validate
    if config.refresh_seconds <= 0:
        raise ValueError("refresh_seconds must be positive")
    if not config.providers:
        logger.warning("No providers configured – app will run but show no status.")
    for p in config.providers:
        if not p.name or not p.type or not p.url:
            raise ValueError(f"Provider {p.name} missing required fields (name/type/url)")
        if not p.components:
            logger.warning(f"Provider '{p.name}' has no components configured")

    logger.info(f"Loaded config with {len(config.providers)} provider(s)")
    return config
