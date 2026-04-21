"""Screen registry and factory."""

import logging
from typing import List

from .base import Screen
from ..config import AppConfig, ScreenConfig

logger = logging.getLogger(__name__)


def create_screens(config: AppConfig) -> List[Screen]:
    """Create screen instances from AppConfig.

    Supports:
      - status_board  -> StatusBoardScreen (live provider fetch)
      - tamagotchi    -> TamagotchiScreen (live JSON fetch + sprites)
      - agent_feed    -> AgentFeedScreen (multi-agent compact list)
      - device_status -> DeviceStatusScreen (local system vitals)
      - opencode      -> OpenCodeScreen (single-agent detail)
      - ui            -> UiTemplateScreen (requires layout: <name>)
    """
    screens: List[Screen] = []

    for sc in config.screens:
        if sc.type == "status_board":
            from .status_board import StatusBoardScreen

            screens.append(StatusBoardScreen(sc))
        elif sc.type == "tamagotchi":
            from .tamagotchi import TamagotchiScreen

            screens.append(TamagotchiScreen(sc))
        elif sc.type == "agent_feed":
            from .agent_feed import AgentFeedScreen

            screens.append(AgentFeedScreen(sc))
        elif sc.type == "device_status":
            from .device_status import DeviceStatusScreen

            screens.append(DeviceStatusScreen(sc))
        elif sc.type == "opencode":
            from .opencode import OpenCodeScreen

            screens.append(OpenCodeScreen(sc))
        elif sc.type == "ui":
            from .ui_template import UiTemplateScreen

            layout_name = sc.layout
            if not layout_name:
                raise ValueError(
                    f"Screen '{sc.name}' has type 'ui' but no layout specified"
                )
            screens.append(UiTemplateScreen(sc, layout_name))
        else:
            raise ValueError(f"Unknown screen type: {sc.type}")

    if not screens:
        from .status_board import StatusBoardScreen

        logger.info("No screens configured, defaulting to status_board")
        screens.append(
            StatusBoardScreen(ScreenConfig(name="Status", type="status_board"))
        )

    logger.info(f"Created {len(screens)} screen(s)")
    return screens
