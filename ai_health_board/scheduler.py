"""Screen-cycling scheduler."""

import asyncio
import logging
import time
from typing import List

from .screens.base import Screen
from .display.base import DisplayBackend

logger = logging.getLogger(__name__)


async def screen_loop(
    screens: List[Screen],
    display: DisplayBackend,
) -> None:
    """Cycle through screens, fetching and rendering as needed.

    For each screen:
    1. If poll_interval has elapsed, fetch new data
    2. Always render when switching screens; skip only if same screen and no change
    3. Sleep for display_duration
    4. Move to next screen
    """
    last_fetch_times: List[float] = [0.0] * len(screens)
    prev_screen_idx: int = -1

    from aiohttp import ClientSession

    async with ClientSession() as session:
        while True:
            for i, screen in enumerate(screens):
                now = time.monotonic()

                if now - last_fetch_times[i] >= screen.poll_interval:
                    try:
                        await screen.fetch(session)
                        last_fetch_times[i] = now
                        logger.debug(
                            f"Fetched data for screen {screen.__class__.__name__}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Fetch failed for screen {screen.__class__.__name__}: {e}"
                        )

                switching = i != prev_screen_idx
                if switching or screen.has_changed():
                    try:
                        img = screen.render(display.width, display.height)
                        display.render_image(img)
                        prev_screen_idx = i
                        logger.debug(f"Rendered screen {screen.__class__.__name__}")
                    except Exception as e:
                        logger.error(
                            f"Render failed for screen {screen.__class__.__name__}: {e}"
                        )

                await asyncio.sleep(screen.display_duration)
