#!/usr/bin/env python3
"""Tamagotchai - AI status companion for Raspberry Pi e-paper displays."""

import asyncio
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ai_health_board.config import load_config, AppConfig, ScreenConfig
from ai_health_board.display import get_display
from ai_health_board.display.base import DisplayBackend
from ai_health_board.screens import create_screens
from ai_health_board.screens.base import Screen
from ai_health_board.screens.status_board import StatusBoardScreen, CategoryData
from ai_health_board.screens.tamagotchi import TamagotchiScreen
from ai_health_board.screens.agent_feed import AgentFeedScreen
from ai_health_board.screens.ui_template import UiTemplateScreen
from ai_health_board.scheduler import screen_loop
from ai_health_board.input import InputManager
from ai_health_board.models import ServiceStatus

APP_NAME = "tamagotchai"
PID_FILE = f"/tmp/{APP_NAME}.pid"

logger = logging.getLogger(__name__)


def _show_images(paths: List[str]) -> None:
    opener = "open" if platform.system() == "Darwin" else "xdg-open"
    for path in paths:
        try:
            subprocess.Popen(
                [opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print(f"  [WARN] {opener} not found; open manually: {path}")
            break


async def _run_once(screens: List[Screen], display: DisplayBackend) -> None:
    from aiohttp import ClientSession

    async with ClientSession() as session:
        for screen in screens:
            try:
                await screen.fetch(session)
                img = screen.render(display.width, display.height)
                display.render_image(img)
                logger.info(f"Rendered screen {screen.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed screen {screen.__class__.__name__}: {e}")


def _inject_mock_status_board(screen: StatusBoardScreen) -> None:
    screen._categories = [
        CategoryData(
            "Claude",
            "anthropic",
            {
                "AI": ServiceStatus.OK,
                "Code": ServiceStatus.OK,
                "API": ServiceStatus.OK,
            },
        ),
        CategoryData(
            "OpenAI",
            "openai",
            {
                "App": ServiceStatus.OK,
                "Chat": ServiceStatus.OK,
                "Web": ServiceStatus.OK,
                "API": ServiceStatus.OK,
            },
        ),
        CategoryData(
            "Lotus",
            "lotus",
            {
                "Live": ServiceStatus.OK,
                "Queue": ServiceStatus.OK,
            },
        ),
    ]
    screen._last_refresh = datetime.now(timezone.utc)


def _inject_mock_tamagotchi(screen: TamagotchiScreen) -> None:
    screen._data = {
        "status": "ok",
        "proxy": True,
        "pending": 2,
        "prs_created": 12,
        "prs_merged": 8,
        "issues_created": 3,
        "comments_resolved": 47,
        "commits_today": 6,
        "lines_changed": 2340,
        "last_action": "merged PR #142",
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "__last_checked": datetime.now(timezone.utc).isoformat(),
    }
    screen._resolve_mood()


def _inject_mock_agent_feed(screen: AgentFeedScreen) -> None:
    screen._agents_data = [
        {
            "name": "OpenCode",
            "status": "working",
            "message": "Refactoring auth module",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        },
        {
            "name": "Cursor",
            "status": "idle",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        },
        {
            "name": "Lotus",
            "status": "success",
            "message": "PR merged",
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        },
    ]


def _demo(
    screens: List[Screen],
    display: DisplayBackend,
    cfg: AppConfig,
    animate: bool = False,
) -> List[str]:
    is_real_hw = cfg.display.backend != "mock"
    output_paths: List[str] = []

    for idx, screen in enumerate(screens):
        if isinstance(screen, StatusBoardScreen):
            _inject_mock_status_board(screen)
            img = screen.render(display.width, display.height)
            display.render_image(img)
            out_path = f"out/demo_status_board_{screen._config.name.lower().replace(' ', '_')}.png"
            img.save(out_path, format="PNG")
            output_paths.append(out_path)
            print(f"  Status board ({screen._config.name}) -> {out_path}")

            if animate:
                anim_paths = _animate_status_board(screen, display)
                output_paths.extend(anim_paths)

        elif isinstance(screen, TamagotchiScreen):
            _inject_mock_tamagotchi(screen)
            num_sprites = len(screen._sprites) or 4
            for frame_idx in range(num_sprites):
                screen._frame = frame_idx
                img = screen.render(display.width, display.height)
                display.render_image(img)
                out_path = f"out/demo_tamagotchi_{screen._config.name.lower().replace(' ', '_')}_f{frame_idx + 1}.png"
                img.save(out_path, format="PNG")
                output_paths.append(out_path)
                print(
                    f"  Tamagotchi {screen._config.name} frame {frame_idx + 1}/{num_sprites} -> {out_path}"
                )
                if is_real_hw and frame_idx == 0:
                    time.sleep(2)
                elif is_real_hw:
                    time.sleep(0.5)

        elif isinstance(screen, AgentFeedScreen):
            _inject_mock_agent_feed(screen)
            img = screen.render(display.width, display.height)
            display.render_image(img)
            out_path = f"out/demo_agent_feed_{screen._config.name.lower().replace(' ', '_')}.png"
            img.save(out_path, format="PNG")
            output_paths.append(out_path)
            print(f"  Agent feed ({screen._config.name}) -> {out_path}")

        else:
            if isinstance(screen, UiTemplateScreen):
                from ui.preview import MOCK_DATA

                screen._data = MOCK_DATA.get(
                    screen._template_name, {"name": screen._config.name}
                )
            img = screen.render(display.width, display.height)
            display.render_image(img)
            tpl = getattr(screen, "_template_name", "")
            label = f"ui:{tpl}" if tpl else screen.__class__.__name__
            safe_name = label.replace(":", "_").replace(" ", "_")
            out_path = f"out/demo_{safe_name}.png"
            img.save(out_path, format="PNG")
            output_paths.append(out_path)
            print(f"  {label} -> {out_path}")

    return output_paths


def _animate_status_board(
    screen: StatusBoardScreen, display: DisplayBackend
) -> List[str]:
    print("  Animating status changes (partial refresh)...")
    output_paths: List[str] = []

    for cat in screen._categories:
        if cat.name == "Claude":
            cat.items["API"] = ServiceStatus.DEGRADED
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    out_path = "out/demo_status_degraded.png"
    img.save(out_path, format="PNG")
    output_paths.append(out_path)
    print(f"    Claude API -> [!] DEGRADED -> {out_path}")
    time.sleep(2)

    for cat in screen._categories:
        if cat.name == "OpenAI":
            cat.items["App"] = ServiceStatus.DOWN
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    out_path = "out/demo_status_down.png"
    img.save(out_path, format="PNG")
    output_paths.append(out_path)
    print(f"    OpenAI App -> [-] DOWN -> {out_path}")
    time.sleep(2)

    for cat in screen._categories:
        for key in list(cat.items.keys()):
            cat.items[key] = ServiceStatus.OK
    screen._last_render_hash = None
    img = screen.render(display.width, display.height)
    display.render_image(img)
    out_path = "out/demo_status_ok.png"
    img.save(out_path, format="PNG")
    output_paths.append(out_path)
    print(f"    All -> [+] OK -> {out_path}")
    time.sleep(1)

    return output_paths


def _demo_ui_templates(output_dir: str = "out") -> List[str]:
    from ui.preview import render_template
    from ui import templates

    output_paths: List[str] = []
    for name in templates.names():
        path = render_template(name, output_dir=output_dir)
        out_path = os.path.join(output_dir, f"demo_ui_{name}.png")
        os.rename(path, out_path)
        output_paths.append(out_path)
        print(f"  ui:{name} -> {out_path}")
    return output_paths


def _demo_contact_sheet(
    paths: List[str], output_path: str = "out/demo_contact_sheet.png"
) -> str:
    from PIL import Image

    images = []
    for p in paths:
        try:
            images.append(Image.open(p))
        except Exception:
            continue

    if not images:
        raise RuntimeError("No images to compose into contact sheet")

    scale = 2
    cols = 4
    rows = (len(images) + cols - 1) // cols
    gap = 4
    label_h = 10

    sample_w, sample_h = images[0].size
    cell_w = sample_w * scale + gap
    cell_h = sample_h * scale + gap + label_h

    sheet_w = cols * cell_w + gap
    sheet_h = rows * cell_h + gap

    sheet = Image.new("1", (sheet_w, sheet_h), 255)

    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(sheet)

    for i, img in enumerate(images):
        col = i % cols
        row = i // cols
        x = gap + col * cell_w
        y = gap + row * cell_h

        resized = img.resize((sample_w * scale, sample_h * scale), Image.NEAREST)
        sheet.paste(resized, (x, y))

        basename = os.path.basename(paths[i]).replace(".png", "").replace("demo_", "")
        label_y = y + sample_h * scale + 1
        draw.text((x, label_y), basename, fill=0)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sheet.save(output_path, format="PNG")
    return output_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} - AI status companion for e-paper displays"
    )
    parser.add_argument(
        "--config",
        default="config",
        help="Config directory (default: config)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    init_parser = subparsers.add_parser("init", help="Interactive setup wizard")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing config files without asking",
    )

    run_parser = subparsers.add_parser("run", help="Run as a long-running service")
    run_parser.add_argument(
        "--once-after",
        type=int,
        default=0,
        help="Initial delay in seconds before first refresh",
    )

    subparsers.add_parser("once", help="Perform one refresh cycle and exit")

    preview_parser = subparsers.add_parser(
        "preview", help="Render a single PNG without hardware"
    )
    preview_parser.add_argument(
        "--show",
        action="store_true",
        help="Open rendered image in system viewer",
    )

    demo_parser = subparsers.add_parser(
        "demo", help="Render each screen with mock data (no network needed)"
    )
    demo_parser.add_argument(
        "--animate",
        action="store_true",
        help="Animate status changes to test partial refresh",
    )
    demo_parser.add_argument(
        "--all",
        action="store_true",
        help="Also render all ui/ templates (boot, idle, error, etc.)",
    )
    demo_parser.add_argument(
        "--contact-sheet",
        action="store_true",
        help="Generate a contact sheet grid of all rendered screens",
    )
    demo_parser.add_argument(
        "--show",
        action="store_true",
        help="Open rendered images in system viewer",
    )

    subparsers.add_parser("doctor", help="Validate configuration and environment")

    ui_preview_parser = subparsers.add_parser(
        "ui-preview", help="Render ui/ templates to PNGs"
    )
    ui_preview_parser.add_argument(
        "--template", "-t", help="Render a single template by name (default: all)"
    )
    ui_preview_parser.add_argument(
        "--output-dir",
        "-o",
        default="out/ui",
        help="Output directory (default: out/ui)",
    )
    ui_preview_parser.add_argument(
        "--contact-sheet", action="store_true", help="Also render a contact sheet grid"
    )
    ui_preview_parser.add_argument(
        "--show",
        action="store_true",
        help="Open rendered images in system viewer",
    )

    args = parser.parse_args()

    from ai_health_board.logging_setup import setup_logging

    setup_logging()

    if args.command == "init":
        from commands.init import run_init

        run_init(config_dir=args.config, force=args.force)
        return

    if args.command == "doctor":
        _doctor(args.config)
        return

    if args.command == "ui-preview":
        _ui_preview(args)
        return

    cfg = load_config(args.config)

    if args.command == "preview":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        out_path = "out/preview.png"
        try:
            if screens:
                img = screens[0].render(display.width, display.height)
                display.render_image(img)
                os.makedirs("out", exist_ok=True)
                img.save(out_path, format="PNG")
        finally:
            display.close()
        print(f"Preview rendered to {out_path}")
        if getattr(args, "show", False):
            _show_images([out_path])
        return

    if args.command == "demo":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        os.makedirs("out", exist_ok=True)
        print("Demo mode: rendering with mock data (no network)")
        try:
            output_paths = _demo(
                screens, display, cfg=cfg, animate=getattr(args, "animate", False)
            )
        finally:
            display.close()

        if getattr(args, "all", False):
            print("\nRendering ui/ templates...")
            ui_paths = _demo_ui_templates()
            output_paths.extend(ui_paths)

        if getattr(args, "contact_sheet", False):
            cs_path = _demo_contact_sheet(output_paths)
            output_paths.append(cs_path)
            print(f"\nContact sheet -> {cs_path}")

        print(f"\nDemo complete. {len(output_paths)} frame(s) rendered to out/")
        if getattr(args, "show", False):
            _show_images(output_paths)
        return

    if args.command == "once":
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        try:
            asyncio.run(_run_once(screens, display))
        finally:
            display.close()
        return

    if args.command == "run":
        logger.info("Starting screen-cycling loop")
        display = get_display(cfg.display)
        screens = create_screens(cfg)
        input_mgr = InputManager(screens)

        if args.once_after:
            logger.info(f"Initial delay {args.once_after}s before first refresh")
            time.sleep(args.once_after)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        input_mgr.setup(loop)
        try:
            loop.run_until_complete(screen_loop(screens, display, input_mgr))
        except KeyboardInterrupt:
            logger.info("Shutting down")
        finally:
            input_mgr.cleanup()
            display.close()
            loop.close()
        return

    parser.print_help()
    sys.exit(1)


def _doctor(config_dir: str) -> None:
    import platform as _platform

    print(f"=== {APP_NAME} Doctor ===")
    print(f"Python: {_platform.python_version()}")

    try:
        cfg = load_config(config_dir)
        print(
            f"Config: loaded ({len(cfg.screens)} screen(s), backend={cfg.display.backend})"
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
        print("aiohttp: MISSING")

    gpio_factory = os.environ.get("GPIOZERO_PIN_FACTORY", "")
    print(f"GPIOZERO_PIN_FACTORY: {gpio_factory or 'NOT SET'}")
    if not gpio_factory:
        print("  Set: export GPIOZERO_PIN_FACTORY=lgpio")

    print("")
    for d in ["/dev/spidev0.0", "/dev/spidev0.1"]:
        print(f"SPI device: {d} - {'EXISTS' if os.path.exists(d) else 'NOT FOUND'}")

    try:
        import lgpio

        print(f"\nlgpio: {lgpio.__version__}")
    except ImportError:
        print("\nlgpio: MISSING (sudo apt install python3-lgpio)")

    for ver in ("V3", "V2", "V4", "V1"):
        try:
            mod_name = f"epd2in13_{ver.lower()}" if ver != "V1" else "epd2in13"
            __import__("waveshare_epd." + mod_name, fromlist=[mod_name])
            print(f"waveshare_epd {ver}: INSTALLED")
            break
        except ImportError:
            print(f"waveshare_epd {ver}: NOT INSTALLED")

    try:
        import subprocess as _sp

        result = _sp.run(
            ["pgrep", "-x", "pisugar-server"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("pisugar-server: RUNNING")
        else:
            print("pisugar-server: NOT RUNNING")
    except Exception:
        print("pisugar-server: UNKNOWN")

    try:
        sock_path = "/tmp/pisugar-server.sock"
        if os.path.exists(sock_path):
            print(f"PiSugar socket: {sock_path} EXISTS")
        else:
            print("PiSugar socket: NOT FOUND")
    except Exception:
        pass

    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        print(f"{APP_NAME} PID: {pid}")
    else:
        print(f"{APP_NAME} PID: NOT SET")

    print(f"\n=== End Doctor ===")


def _ui_preview(args) -> None:
    from ui.preview import render_all, render_template
    from ui.preview.contact_sheet import render_contact_sheet

    os.makedirs(args.output_dir, exist_ok=True)
    output_paths: List[str] = []
    if args.template:
        print(f"Rendering template: {args.template}")
        path = render_template(args.template, output_dir=args.output_dir)
        output_paths.append(path)
        print(f"  -> {path}")
    else:
        print(f"Rendering all templates to {args.output_dir}/")
        paths = render_all(output_dir=args.output_dir)
        output_paths.extend(paths)
        for p in paths:
            print(f"  {os.path.basename(p)}")
        print(f"\n{len(paths)} template(s) rendered.")

    if args.contact_sheet:
        cs_path = os.path.join(args.output_dir, "contact_sheet.png")
        render_contact_sheet(output_path=cs_path)
        output_paths.append(cs_path)
        print(f"Contact sheet -> {cs_path}")

    if getattr(args, "show", False):
        _show_images(output_paths)


if __name__ == "__main__":
    main()
