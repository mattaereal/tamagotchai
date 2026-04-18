#!/usr/bin/env python3
"""Main entrypoint for the AI health board application."""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ai_health_board.config import load_config, AppConfig
from ai_health_board.display import get_display
from ai_health_board.display.base import DisplayBackend
from ai_health_board.screens import create_screens
from ai_health_board.screens.base import Screen
from ai_health_board.screens.health import HealthScreen
from ai_health_board.screens.tamagotchi import TamagotchiScreen
from ai_health_board.scheduler import screen_loop
from ai_health_board.cache import load_cache
from ai_health_board.models import (
    AppState,
    ServiceStatus,
    ProviderStatus,
    ComponentStatus,
    LotusHealthStatus,
    LotusStatsData,
)

logger = logging.getLogger(__name__)


async def _run_once(screens: List[Screen], display: DisplayBackend) -> None:
    """Fetch and render all screens once."""
    from aiohttp import ClientSession

    async with ClientSession() as session:
        for i, screen in enumerate(screens):
            try:
                await screen.fetch(session)
                img = screen.render(display.width, display.height)
                display.render_image(img)
                logger.info(f"Rendered screen {screen.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed screen {screen.__class__.__name__}: {e}")


def _build_mock_health_state() -> AppState:
    """Build a mock AppState with all providers OK."""
    return AppState(
        last_refresh=datetime.now(timezone.utc),
        providers=[
            ProviderStatus(
                name="Claude",
                provider_type="statuspage",
                status=ServiceStatus.OK,
                components=[
                    ComponentStatus("claude.ai", ServiceStatus.OK),
                    ComponentStatus("Claude Code", ServiceStatus.OK),
                    ComponentStatus("Claude API (api.anthropic.com)", ServiceStatus.OK),
                ],
            ),
            ProviderStatus(
                name="OpenAI",
                provider_type="statuspage",
                status=ServiceStatus.OK,
                components=[
                    ComponentStatus("App", ServiceStatus.OK),
                    ComponentStatus("Conversations", ServiceStatus.OK),
                    ComponentStatus("Codex Web", ServiceStatus.OK),
                    ComponentStatus("Codex API", ServiceStatus.OK),
                ],
            ),
            ProviderStatus(
                name="Lotus",
                provider_type="lotus_health",
                status=ServiceStatus.OK,
                components=[
                    ComponentStatus("Lotus", ServiceStatus.OK),
                    ComponentStatus("Queue", ServiceStatus.OK),
                ],
            ),
        ],
        stale=False,
    )


def _inject_mock_health(screen: HealthScreen) -> None:
    """Inject mock provider data into a health screen."""
    screen._state = _build_mock_health_state()


def _inject_mock_tamagotchi(screen: TamagotchiScreen) -> None:
    """Inject mock health + stats data into a tamagotchi screen."""
    screen._health = LotusHealthStatus(
        status="ok",
        proxy=True,
        pending=2,
        last_checked=datetime.now(timezone.utc),
    )
    screen._stats = LotusStatsData(
        prs_created=12,
        prs_merged=8,
        issues_created=3,
        comments_resolved=47,
        commits_today=6,
        lines_changed=2340,
        uptime_seconds=86400,
        last_action="merged PR #142",
        last_action_time=datetime.now(timezone.utc),
    )


def _demo(
    screens: List[Screen], display: DisplayBackend, animate: bool = False
) -> None:
    """Render each screen with mock data, cycling tamagotchi through all 4 sprites."""
    for screen in screens:
        if isinstance(screen, HealthScreen):
            _inject_mock_health(screen)
            img = screen.render(display.width, display.height)
            display.render_image(img)
            print("  Health screen rendered -> out/frame.png")

            if animate:
                _animate_health(screen, display)

        elif isinstance(screen, TamagotchiScreen):
            _inject_mock_tamagotchi(screen)
            num_sprites = len(screen._sprites) or 4
            for frame_idx in range(num_sprites):
                screen._frame = frame_idx
                img = screen.render(display.width, display.height)
                display.render_image(img)
                out_path = f"out/demo_tamagotchi_f{frame_idx + 1}.png"
                img.save(out_path, format="PNG")
                print(f"  Tamagotchi frame {frame_idx + 1}/{num_sprites} -> {out_path}")
                time.sleep(0.3)
            final_path = "out/frame.png"
            img.save(final_path, format="PNG")


def _animate_health(screen: HealthScreen, display: DisplayBackend) -> None:
    """Animate health screen status changes to test partial refresh."""
    state = screen._state
    if not state:
        return

    print("  Animating status changes (partial refresh)...")

    # Step 1: Claude API -> DEGRADED
    for prov in state.providers:
        for comp in prov.components:
            if "API" in comp.name and prov.name == "Claude":
                comp.status = ServiceStatus.DEGRADED
                prov.status = ServiceStatus.DEGRADED
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    img.save("out/demo_health_degraded.png", format="PNG")
    print("    Claude API -> [!] DEGRADED")
    time.sleep(2)

    # Step 2: OpenAI App -> DOWN
    for prov in state.providers:
        for comp in prov.components:
            if comp.name == "App" and prov.name == "OpenAI":
                comp.status = ServiceStatus.DOWN
                prov.status = ServiceStatus.DOWN
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    img.save("out/demo_health_down.png", format="PNG")
    print("    OpenAI App -> [-] DOWN")
    time.sleep(2)

    # Step 3: Restore all to OK
    for prov in state.providers:
        prov.status = ServiceStatus.OK
        for comp in prov.components:
            comp.status = ServiceStatus.OK
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    img.save("out/demo_health_ok.png", format="PNG")
    print("    All -> [+] OK")
    time.sleep(1)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="AI health status board for Raspberry Pi e-paper display"
    )
    parser.add_argument(
        "--config",
        default="config/providers.yaml",
        help="Path to providers YAML config",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    run_parser = subparsers.add_parser("run", help="Run as a long-running service")
    run_parser.add_argument(
        "--once-after",
        type=int,
        default=0,
        help="Initial delay in seconds before first refresh",
    )

    subparsers.add_parser("once", help="Perform one refresh cycle and exit")

    subparsers.add_parser("preview", help="Render a single PNG without hardware")

    demo_parser = subparsers.add_parser(
        "demo", help="Render each screen with mock data (no network needed)"
    )
    demo_parser.add_argument(
        "--animate",
        action="store_true",
        help="Animate status changes to test partial refresh",
    )

    subparsers.add_parser("doctor", help="Validate configuration and environment")

    args = parser.parse_args()

    from ai_health_board.logging_setup import setup_logging

    setup_logging()

    if args.command == "doctor":
        import platform

        print("=== Doctor Check ===")
        print(f"Python: {platform.python_version()}")
        try:
            cfg = load_config(args.config)
            print(
                f"Config: loaded ({len(cfg.providers)} provider(s), {len(cfg.screens)} screen(s))"
            )
        except Exception as e:
            print(f"Config: ERROR - {e}")
            sys.exit(1)

        try:
            import ai_health_board

            print("Imports: OK")
        except Exception as e:
            print(f"Imports: FAIL - {e}")

        try:
            import aiohttp

            print(f"aiohttp: {aiohttp.__version__}")
        except ImportError:
            print("aiohttp: MISSING (install with: pip install aiohttp)")

        gpio_factory = os.environ.get("GPIOZERO_PIN_FACTORY", "")
        print(f"GPIOZERO_PIN_FACTORY: {gpio_factory or 'NOT SET'}")
        if not gpio_factory:
            print("  Set: export GPIOZERO_PIN_FACTORY=lgpio")

        print("")
        spi_devs = ["/dev/spidev0.0", "/dev/spidev0.1"]
        spi_found = False
        for d in spi_devs:
            if os.path.exists(d):
                print(f"SPI device: {d} - EXISTS")
                spi_found = True
            else:
                print(f"SPI device: {d} - NOT FOUND")

        if not spi_found:
            print("  Enable: sudo raspi-config -> Interface Options -> SPI -> Enable")

        try:
            import lgpio

            print(f"\nlgpio: {lgpio.__version__}")
        except ImportError:
            print("\nlgpio: MISSING (sudo apt install python3-lgpio)")

        try:
            from waveshare_epd import epd2in13_V3

            print("waveshare_epd V3: INSTALLED")
        except ImportError:
            print("waveshare_epd V3: NOT INSTALLED")
            print("  git clone https://github.com/waveshareteam/e-Paper.git")
            print("  cd e-Paper/RaspberryPi_JetsonNano/python")
            print("  sudo apt install -y python3-setuptools")
            print("  sudo python3 setup.py install")

        print("\n=== End Doctor ===")
        return

    cfg = load_config(args.config)

    if args.command == "preview":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        if screens:
            img = screens[0].render(display.width, display.height)
            display.render_image(img)
        print("Preview rendered to out/frame.png")
        return

    if args.command == "demo":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        os.makedirs("out", exist_ok=True)
        print("Demo mode: rendering with mock data (no network)")
        _demo(screens, display, animate=getattr(args, "animate", False))
        print("Demo complete. Check out/ for rendered frames.")
        return

    if args.command == "once":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        asyncio.run(_run_once(screens, display))
        display.close()
        return

    if args.command == "run":
        logger.info("Starting screen-cycling loop")
        display = get_display(cfg.display)
        screens = create_screens(cfg)

        if args.once_after:
            logger.info(f"Initial delay {args.once_after}s before first refresh")
            time.sleep(args.once_after)

        try:
            asyncio.run(screen_loop(screens, display))
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            display.close()
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
