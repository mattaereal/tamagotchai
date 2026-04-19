"""Input handling for PiSugar button signals.

Listens for SIGUSR1 (single tap -> next screen) and
SIGUSR2 (double tap -> jump to tamagotchi) via process signals.
Writes PID file so pisugar-server shell commands can target this process.
"""

import asyncio
import logging
import os
import signal
import time as _time
from typing import List, Optional

from .screens.base import Screen
from .screens.tamagotchi import TamagotchiScreen

logger = logging.getLogger(__name__)

PID_FILE = "/tmp/tamagotchai.pid"
_DEBOUNCE_SECONDS = 0.5


class InputManager:
    def __init__(self, screens: List[Screen], debounce: float = _DEBOUNCE_SECONDS):
        self._screens = screens
        self.next_screen = asyncio.Event()
        self.jump_tamagotchi = asyncio.Event()
        self._tamagotchi_idx: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._debounce = debounce
        self._last_signal_time: float = 0.0

        for i, s in enumerate(screens):
            if isinstance(s, TamagotchiScreen):
                self._tamagotchi_idx = i
                logger.info(f"Tamagotchi screen at index {i}")
                break

    def setup(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._write_pid()
        loop.add_signal_handler(signal.SIGUSR1, self._on_sigusr1)
        loop.add_signal_handler(signal.SIGUSR2, self._on_sigusr2)
        logger.info("Input handlers registered (SIGUSR1=next, SIGUSR2=tamagotchi)")

    def cleanup(self) -> None:
        self._remove_pid()
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.remove_signal_handler(signal.SIGUSR1)
                self._loop.remove_signal_handler(signal.SIGUSR2)
            except (OSError, ValueError):
                pass
        logger.debug("Input handlers cleaned up")

    @property
    def tamagotchi_idx(self) -> Optional[int]:
        return self._tamagotchi_idx

    def _on_sigusr1(self) -> None:
        now = _time.monotonic()
        if now - self._last_signal_time < self._debounce:
            logger.debug("SIGUSR1 debounced (too soon after last signal)")
            return
        self._last_signal_time = now
        logger.info("SIGUSR1 received -> next screen")
        self.next_screen.set()

    def _on_sigusr2(self) -> None:
        now = _time.monotonic()
        if now - self._last_signal_time < self._debounce:
            logger.debug("SIGUSR2 debounced (too soon after last signal)")
            return
        self._last_signal_time = now
        logger.info("SIGUSR2 received -> jump to tamagotchi")
        self.jump_tamagotchi.set()

    def _write_pid(self) -> None:
        try:
            with open(PID_FILE, "w") as f:
                f.write(str(os.getpid()))
            logger.debug(f"PID {os.getpid()} written to {PID_FILE}")
        except OSError as e:
            logger.warning(f"Failed to write PID file: {e}")

    def _remove_pid(self) -> None:
        try:
            os.unlink(PID_FILE)
        except OSError:
            pass
