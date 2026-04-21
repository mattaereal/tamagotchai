"""Tests for InputManager and scheduler interruption."""

import asyncio
import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.input import InputManager, PID_FILE
from core.screens.status_board import StatusBoardScreen
from core.screens.tamagotchi import TamagotchiScreen
from core.screens.base import Screen
from core.config import ScreenConfig
from core.scheduler import _interruptible_sleep


def _cleanup_pid():
    try:
        os.unlink(PID_FILE)
    except OSError:
        pass


# --- InputManager basic ---


def test_input_manager_no_tamagotchi():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)
    assert mgr.tamagotchi_idx is None


def test_input_manager_with_tamagotchi():
    sc1 = ScreenConfig(name="Test", type="status_board")
    sc2 = ScreenConfig(name="Lotus", type="tamagotchi", url="http://test")
    screens = [StatusBoardScreen(sc1), TamagotchiScreen(sc2)]
    mgr = InputManager(screens)
    assert mgr.tamagotchi_idx == 1


def test_input_manager_tamagotchi_first():
    sc1 = ScreenConfig(name="Lotus", type="tamagotchi", url="http://test")
    sc2 = ScreenConfig(name="Test", type="status_board")
    screens = [TamagotchiScreen(sc1), StatusBoardScreen(sc2)]
    mgr = InputManager(screens)
    assert mgr.tamagotchi_idx == 0


def test_input_manager_events_start_cleared():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)
    assert not mgr.next_screen.is_set()
    assert not mgr.jump_tamagotchi.is_set()


def test_input_manager_pid_file():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)
    try:
        loop = asyncio.new_event_loop()
        mgr.setup(loop)
        assert os.path.exists(PID_FILE)
        with open(PID_FILE) as f:
            assert f.read().strip() == str(os.getpid())
    finally:
        mgr.cleanup()
        loop.close()
        _cleanup_pid()


def test_input_manager_cleanup_removes_pid():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)
    loop = asyncio.new_event_loop()
    mgr.setup(loop)
    assert os.path.exists(PID_FILE)
    mgr.cleanup()
    loop.close()
    assert not os.path.exists(PID_FILE)


# --- Signal handling ---


def test_sigusr1_sets_next_screen():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens, debounce=0.0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mgr.setup(loop)

    try:
        assert not mgr.next_screen.is_set()
        os.kill(os.getpid(), signal.SIGUSR1)
        loop.call_soon_threadsafe(lambda: None)
        loop.run_until_complete(asyncio.sleep(0.05))
        assert mgr.next_screen.is_set()
    finally:
        mgr.cleanup()
        loop.close()
        _cleanup_pid()


def test_sigusr2_sets_jump_tamagotchi():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens, debounce=0.0)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mgr.setup(loop)

    try:
        assert not mgr.jump_tamagotchi.is_set()
        os.kill(os.getpid(), signal.SIGUSR2)
        loop.call_soon_threadsafe(lambda: None)
        loop.run_until_complete(asyncio.sleep(0.05))
        assert mgr.jump_tamagotchi.is_set()
    finally:
        mgr.cleanup()
        loop.close()
        _cleanup_pid()


def test_debounce_ignores_rapid_signals():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens, debounce=0.5)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    mgr.setup(loop)

    try:
        os.kill(os.getpid(), signal.SIGUSR1)
        loop.call_soon_threadsafe(lambda: None)
        loop.run_until_complete(asyncio.sleep(0.02))
        assert mgr.next_screen.is_set()

        mgr.next_screen.clear()
        os.kill(os.getpid(), signal.SIGUSR1)
        loop.call_soon_threadsafe(lambda: None)
        loop.run_until_complete(asyncio.sleep(0.02))
        assert not mgr.next_screen.is_set()
    finally:
        mgr.cleanup()
        loop.close()
        _cleanup_pid()


# --- Interruptible sleep ---


def test_interruptible_sleep_no_manager():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start = time.monotonic()
        interrupted = loop.run_until_complete(_interruptible_sleep(0.1, None))
        elapsed = time.monotonic() - start
        assert not interrupted
        assert elapsed >= 0.08
    finally:
        loop.close()


def test_interruptible_sleep_full_duration():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        start = time.monotonic()
        interrupted = loop.run_until_complete(_interruptible_sleep(0.1, mgr))
        elapsed = time.monotonic() - start
        assert not interrupted
        assert elapsed >= 0.08
    finally:
        loop.close()


def test_interruptible_sleep_interrupted_by_next_screen():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _trigger():
        await asyncio.sleep(0.02)
        mgr.next_screen.set()

    try:
        start = time.monotonic()
        interrupted = loop.run_until_complete(
            asyncio.gather(
                _interruptible_sleep(5, mgr),
                _trigger(),
            )
        )[0]
        elapsed = time.monotonic() - start
        assert interrupted
        assert elapsed < 1.0
    finally:
        loop.close()


def test_interruptible_sleep_interrupted_by_jump_tamagotchi():
    sc = ScreenConfig(name="Test", type="status_board")
    screens = [StatusBoardScreen(sc)]
    mgr = InputManager(screens)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _trigger():
        await asyncio.sleep(0.02)
        mgr.jump_tamagotchi.set()

    try:
        start = time.monotonic()
        interrupted = loop.run_until_complete(
            asyncio.gather(
                _interruptible_sleep(5, mgr),
                _trigger(),
            )
        )[0]
        elapsed = time.monotonic() - start
        assert interrupted
        assert elapsed < 1.0
    finally:
        loop.close()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
