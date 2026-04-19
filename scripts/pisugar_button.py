#!/usr/bin/env python3
"""PiSugar S button daemon -- GPIO3 direct input.

Listens on GPIO3 (pin 5) with pull-up and debounce.
- Short press: send SIGUSR1 to tamagotchi (next screen)
- Long press (>= 1.2s): attempt shutdown screen, then sudo shutdown -h now

Run on Pi only. Requires: python3-gpiozero, GPIOZERO_PIN_FACTORY=lgpio
"""

import logging
import os
import signal
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pisugar_button")

LONG_PRESS_SECONDS = 1.2
POLL_INTERVAL = 0.05
PID_FILE = "/tmp/tamagotchai.pid"


def handle_short_press():
    logger.info("SHORT PRESS detected")
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE) as f:
                pid = f.read().strip()
            if pid.isdigit():
                os.kill(int(pid), signal.SIGUSR1)
                logger.info(f"Sent SIGUSR1 to tamagotchai (PID {pid})")
                return
    except (OSError, ProcessLookupError) as e:
        logger.warning(f"Could not signal tamagotchai: {e}")
    logger.info("No tamagotchai process to signal")


def handle_long_press():
    logger.info("LONG PRESS detected -> shutting down")
    try:
        subprocess.run(
            [
                sys.executable,
                os.path.join(os.path.dirname(__file__), "..", "app.py"),
                "once",
            ],
            env={**os.environ, "SHUTDOWN_SCREEN": "1"},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Shutdown screen failed: {e}")
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)


def main():
    try:
        from gpiozero import Button
    except ImportError:
        logger.error("gpiozero not installed. Run: sudo apt install python3-gpiozero")
        sys.exit(1)

    pin_factory = os.environ.get("GPIOZERO_PIN_FACTORY", "")
    if not pin_factory:
        logger.warning(
            "GPIOZERO_PIN_FACTORY not set. On Trixie, run: export GPIOZERO_PIN_FACTORY=lgpio"
        )

    logger.info("Starting PiSugar button daemon on GPIO3 (pin 5)")
    logger.info(f"Long press threshold: {LONG_PRESS_SECONDS}s")

    btn = Button(
        3,
        pull_up=True,
        bounce_time=0.15,
    )

    press_time = None

    def on_press():
        nonlocal press_time
        press_time = time.monotonic()
        logger.debug("GPIO3 pressed")

    def on_release():
        nonlocal press_time
        if press_time is None:
            return
        held = time.monotonic() - press_time
        press_time = None
        logger.debug(f"GPIO3 released after {held:.2f}s")
        if held >= LONG_PRESS_SECONDS:
            handle_long_press()
        else:
            handle_short_press()

    btn.when_pressed = on_press
    btn.when_released = on_release

    logger.info("Button daemon ready. Waiting for presses...")

    try:
        signal.pause()
    except KeyboardInterrupt:
        logger.info("Shutting down button daemon")


if __name__ == "__main__":
    main()
