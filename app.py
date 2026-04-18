#!/usr/bin/env python3
"""Main entrypoint for the AI health board application."""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

from ai_health_board.config import load_config, AppConfig
from ai_health_board.display import get_display
from ai_health_board.providers import get_provider
from ai_health_board.render import render_state
from ai_health_board.scheduler import poll_loop
from ai_health_board.cache import load_cache, save_cache
from ai_health_board.models import AppState, ServiceStatus, ProviderStatus

logger = logging.getLogger(__name__)


def build_state(config: AppConfig) -> None:
    """Fetch all providers and build the aggregated state dict."""
    cache = load_cache() or {}

    async def run_once() -> None:
        from aiohttp import ClientSession

        async with ClientSession() as session:
            # Create provider instances from config
            providers = []
            for provider_config in config.providers:
                try:
                    provider = get_provider(provider_config)
                    providers.append(provider)
                except Exception as e:
                    logger.error(
                        f"Failed to create provider {provider_config.name}: {e}"
                    )

            # Fetch status from all providers
            tasks = [provider.get_status(session) for provider in providers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved: List[Optional[ProviderStatus]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Provider fetch failed: {r}")
                resolved.append(None)
            else:
                resolved.append(r)

        state = AppState(
            last_refresh=datetime.utcnow(),
            providers=[r for r in resolved if r is not None],
            stale=False,
        )

        # Merge with cache for missing providers / components
        if cache and "providers" in cache:
            cached_provs = {p["name"]: p for p in cache["providers"]}
            for prov in state.providers:
                if prov.name in cached_provs:
                    cached = cached_provs[prov.name]
                    cached_map = {
                        c["name"]: c["status"] for c in cached.get("components", [])
                    }
                    for comp in prov.components:
                        if (
                            comp.status == ServiceStatus.UNKNOWN
                            and comp.name in cached_map
                        ):
                            comp.status = ServiceStatus(cached_map[comp.name])
                            comp.failure_count = cached.get("consecutive_failures", 0)

        save_cache(state.to_dict())
        render_state(state.to_dict(), config.display)

    try:
        asyncio.run(run_once())
    except Exception as e:
        logger.exception(f"Run failed: {e}")
        sys.exit(1)


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

    # run command
    run_parser = subparsers.add_parser("run", help="Run as a long-running service")
    run_parser.add_argument(
        "--once-after",
        type=int,
        default=0,
        help="Initial delay in seconds before first refresh",
    )

    # once command
    subparsers.add_parser("once", help="Perform one refresh cycle and exit")

    # preview command
    subparsers.add_parser("preview", help="Render a single PNG without hardware")

    # doctor command
    subparsers.add_parser("doctor", help="Validate configuration and environment")

    args = parser.parse_args()

    # Setup logging before anything else
    from ai_health_board.logging_setup import setup_logging

    setup_logging()

    if args.command == "doctor":
        import platform
        import os

        print("=== Doctor Check ===")
        print(f"Python: {platform.python_version()}")
        try:
            cfg = load_config(args.config)
            print(f"Config: loaded ({len(cfg.providers)} provider(s))")
        except Exception as e:
            print(f"Config: ERROR – {e}")
            sys.exit(1)

        try:
            import ai_health_board

            print("Imports: OK")
        except Exception as e:
            print(f"Imports: FAIL – {e}")

        # Check aiohttp
        try:
            import aiohttp

            print(f"aiohttp: {aiohttp.__version__}")
        except ImportError:
            print("aiohttp: MISSING (install with: pip install aiohttp)")

        # SPI detection
        print("")
        spi_devs = ["/dev/spidev0.0", "/dev/spidev0.1"]
        spi_found = False
        for d in spi_devs:
            if os.path.exists(d):
                print(f"SPI device: {d} – EXISTS")
                spi_found = True
            else:
                print(f"SPI device: {d} – NOT FOUND")

        if not spi_found:
            print("\n[WARNING] No SPI devices found!")
            print("Enable SPI on Raspberry Pi OS:")
            print("  sudo raspi-config -> Interface Options -> SPI -> Enable -> Reboot")

        # Waveshare check
        try:
            from waveshare_epd import epd2in13

            print("\nwaveshare_epd: INSTALLED (e-paper hardware ready)")
        except ImportError:
            print("\nwaveshare_epd: NOT INSTALLED")
            print("To install for e-paper display:")
            print("  git clone https://github.com/waveshareteam/e-Paper.git")
            print("  cd e-Paper/RaspberryPi_JetsonNano/python")
            print("  sudo python3 setup.py install")

        print("\n=== End Doctor ===")
        return

    cfg = load_config(args.config)

    if args.command == "preview":
        cache = load_cache() or {}
        render_state(
            {
                "last_refresh": None,
                "stale": True,
                "providers": cache.get("providers", []),
            },
            cfg.display,
        )
        print("Preview rendered to out/frame.png")
        return

    if args.command == "once":
        build_state(cfg)
        return

    if args.command == "run":
        logger.info("Starting long-running refresh loop")
        poll_loop(
            lambda: build_state(cfg),
            refresh_seconds=cfg.refresh_seconds,
            initial_delay=args.once_after,
        )
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
