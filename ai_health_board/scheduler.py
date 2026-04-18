"""Simple polling scheduler."""
import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


def poll_loop(
    work_fn: Callable[[], None],
    refresh_seconds: int,
    *,
    initial_delay: int = 0,
) -> None:
    """Run work_fn repeatedly with a fixed interval.

    Args:
        work_fn: Function that performs one fetch+render cycle.
        refresh_seconds: Interval between cycles.
        initial_delay: Seconds to wait before first run.
    """
    if initial_delay:
        logger.info(f"Initial delay {initial_delay}s before first refresh")
        time.sleep(initial_delay)

    while True:
        try:
            work_fn()
        except Exception as e:  # pylint: disable=broad-except
            # Never let the loop die due to an uncaught error
            logger.exception(f"Unexpected error in poll loop: {e}")
        time.sleep(refresh_seconds)
