#!/usr/bin/env python3
"""Main entrypoint for the AI health board application."""
import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

from ai_health_board.config import load_config
from ai_health_board.display import get_display
from ai_health_board.providers import get_provider
from ai_health_board.render import render_state
from ai_health_board.scheduler import poll_loop
from ai_health_board.cache import load_cache
from ai_health_board.models import AppState, ServiceStatus

logger = logging.getLogger(__name__)
def build_state(config) -> Dict[str, object]:
    """Fetch all providers and build the aggregated state dict."""
    cache = load_cache() or {}
    state = AppState(
        last_refresh=None,
        providers=[],
        stale=False,
    )

    async def run_once() -> None:
        nonlocal state
        from aiohttp import ClientSession
        async with ClientSession() as session:
            tasks = [get_provider(p).get_status(session) for p in config.providers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        resolved: List[Optional[object]] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"Provider fetch failed: {r}")
                resolved.append(None)
            else:
                resolved.append(r)

        state.providers = [r for r in resolved if r is not None]
        state.last_refresh = datetime.utcnow()
        state.stale = False

        # Merge with cache for missing providers / components
        if cache and "providers" in cache:
            cached_provs = {p["name"]: p for p in cache["providers"]}
            for prov in state.providers:
                if prov.name in cached_provs:
                    cached = cached_provs[prov.name]
                    cached_map = {c["name"]: c["status"] for c in cached.get("components", [])}
                    for comp in prov.components:
                        if comp.status == ServiceStatus.UNKNOWN and comp.name in cached_map:
                            comp.status = ServiceStatus(cached_map[comp.name])
                            comp.failure_count = cached.get("consecutive_failures", 0)

        save_cache(state.to_dict())
        render_state(state.to_dict(), config.display.__dict__)

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
        import platform, os

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

        # SPI detection
        spi_devs = ["/dev/spidev0.0", "/dev/spidev0.1"]
        for d in spi_devs:
            if os.path.exists(d):
                print(f"SPI device: {d} (exists)")
            else:
                print(f"SPI device: {d} (not found)")
        print("\nTo enable SPI on Raspberry Pi OS:")
        print("  sudo raspi-config -> Interface Options -> SPI -> Enable")
        print("=== End Doctor ===")
        return

    cfg = load_config(args.config)

    if args.command == "preview":
        display = get_display(cfg.display.__dict__)
        cache = load_cache() or {}
        render_state(
            {
                "last_refresh": None,
                "stale": True,
                "providers": cache.get("providers", []),
            },
            cfg.display.__dict__,
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
def render_state(state: Dict[str, object], display_cfg: Dict[str, object]) -> None:
    """Render state to configured display backend."""
    from ai_health_board.display import get_display

    display = get_display(display_cfg)
    display.render(state)
    display.flush()
if __name__ == "__main__":
    main()
