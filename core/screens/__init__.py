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
      - ui:<name>     -> UiTemplateScreen (wraps any registered ui/ template)
      - <ui name>     -> UiTemplateScreen (if name matches a ui/ template)
    """
    screens: List[Screen] = []

    for sc in config.screens:
        if sc.template == "status_board":
            from .status_board import StatusBoardScreen

            screens.append(StatusBoardScreen(sc))
        elif sc.template == "tamagotchi":
            from .tamagotchi import TamagotchiScreen

            screens.append(TamagotchiScreen(sc))
        elif sc.template == "agent_feed":
            from .agent_feed import AgentFeedScreen

            screens.append(AgentFeedScreen(sc))
        elif sc.template == "device_status":
            from .device_status import DeviceStatusScreen

            screens.append(DeviceStatusScreen(sc))
        elif sc.template == "opencode":
            from .opencode import OpenCodeScreen

            screens.append(OpenCodeScreen(sc))
        else:
            from .ui_template import UiTemplateScreen

            if UiTemplateScreen.is_ui_template(sc.template):
                tpl_name = UiTemplateScreen.strip_prefix(sc.template)
                screens.append(UiTemplateScreen(sc, tpl_name))
            else:
                raise ValueError(f"Unknown screen template: {sc.template}")

    if not screens:
        from .status_board import StatusBoardScreen

        logger.info("No screens configured, defaulting to status_board")
        screens.append(
            StatusBoardScreen(ScreenConfig(name="Status", template="status_board"))
        )

    logger.info(f"Created {len(screens)} screen(s)")
    return screens
