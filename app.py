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

from core.config import load_config, AppConfig, ScreenConfig
from core.display import get_display
from core.display.base import DisplayBackend
from core.screens import create_screens
from core.screens.base import Screen
from core.screens.status_board import StatusBoardScreen, CategoryData
from core.screens.tamagotchi import TamagotchiScreen
from core.screens.agent_feed import AgentFeedScreen
from core.screens.device_status import DeviceStatusScreen
from core.screens.ui_template import UiTemplateScreen
from core.scheduler import screen_loop
from core.input import InputManager
from core.models import ServiceStatus

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


def _inject_mock_tamagotchi(screen: TamagotchiScreen, status: str = "ok") -> None:
    screen._data = {
        "status": status,
        "proxy": True,
        "pending": 2 if status == "working" else 0,
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


def _inject_mock_agent_feed(screen: AgentFeedScreen, scenario: str = "mixed") -> None:
    scenarios = {
        "mixed": [
            {
                "name": "OpenCode",
                "status": "working",
                "message": "cmd: git commit",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "model": "anthropic/claude-3.7-sonnet",
                    "tokens_input": 1240,
                    "tokens_output": 340,
                    "cost_usd": 0.0042,
                    "project": "tamagotchai",
                    "message_count": 5,
                    "files_modified": 3,
                },
            },
        ],
        "idle": [
            {
                "name": "OpenCode",
                "status": "idle",
                "message": "",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "project": "tamagotchai",
                    "message_count": 12,
                },
            },
        ],
        "waiting": [
            {
                "name": "OpenCode",
                "status": "waiting_input",
                "message": "needs permission: bash",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "project": "tamagotchai",
                    "tool_name": "bash",
                },
            },
        ],
        "hint": [
            {
                "name": "OpenCode",
                "status": "error",
                "__fetch_error": True,
            },
        ],
    }
    screen._agents_data = scenarios.get(scenario, scenarios["mixed"])


def _inject_mock_device_status(screen: DeviceStatusScreen) -> None:
    screen._data = {
        "hostname": "tamagotchai.local",
        "ip": "192.168.1.42",
        "ssid": "Vault-TecNet",
        "bssid": "AA:BB:CC:DD:EE:FF",
        "wifi_status": "connected",
        "signal": "85%",
        "cpu_temp": "52.3C",
        "memory": "234/512MB",
        "disk": "3.2/28GB",
        "uptime": "2d 4h 32m",
        "battery": "87%",
        "battery_charging": True,
        "pid": "12345",
        "version": "1.0.0",
    }


class DemoSequence:
    def __init__(
        self,
        display: DisplayBackend,
        cfg: AppConfig,
        output_dir: str = "out/demo_frames",
        fast: bool = False,
    ):
        self._display = display
        self._cfg = cfg
        self._output_dir = output_dir
        self._fast = fast
        self._frames: List[str] = []
        self._frame_idx = 0
        self._is_real_hw = cfg.display.backend != "mock"
        os.makedirs(output_dir, exist_ok=True)

    def _delay(self, seconds: float) -> None:
        if self._fast:
            return
        if self._is_real_hw:
            time.sleep(seconds)
        else:
            time.sleep(min(seconds, 0.3))

    def _save_frame(self, label: str, img) -> str:
        self._frame_idx += 1
        safe = label.lower().replace(" ", "_").replace(":", "_")
        filename = f"{self._frame_idx:03d}_{safe}.png"
        path = os.path.join(self._output_dir, filename)
        img.save(path, format="PNG")
        self._frames.append(path)
        return path

    def _render(self, label: str, img, display_duration: float = 3.0) -> str:
        self._display.render_image(img)
        path = self._save_frame(label, img)
        print(f"  [{label}] -> {path}")
        self._delay(display_duration)
        return path

    def boot(self) -> str:
        from ui.templates import render as tpl_render
        from ui.preview import MOCK_DATA

        img = tpl_render("boot", MOCK_DATA["boot"])
        return self._render("Boot", img, 3.0)

    def status_board_ok(self, screen: StatusBoardScreen) -> str:
        _inject_mock_status_board(screen)
        screen._last_render_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render("Status: All OK", img, 4.0)

    def status_board_degraded(self, screen: StatusBoardScreen) -> str:
        for cat in screen._categories:
            if cat.name == "Claude":
                cat.items["API"] = ServiceStatus.DEGRADED
        screen._last_render_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render("Status: Degraded", img, 3.0)

    def status_board_down(self, screen: StatusBoardScreen) -> str:
        for cat in screen._categories:
            if cat.name == "OpenAI":
                cat.items["App"] = ServiceStatus.DOWN
        screen._last_render_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render("Status: Down", img, 3.0)

    def status_board_recovered(self, screen: StatusBoardScreen) -> str:
        for cat in screen._categories:
            for key in list(cat.items.keys()):
                cat.items[key] = ServiceStatus.OK
        screen._last_render_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render("Status: Recovered", img, 3.0)

    def tamagotchi_mood(self, screen: TamagotchiScreen, status: str, label: str) -> str:
        _inject_mock_tamagotchi(screen, status)
        screen._last_render_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render(f"Tamagotchi: {label}", img, 3.0)

    def agent_feed(self, screen: AgentFeedScreen, scenario: str, label: str) -> str:
        _inject_mock_agent_feed(screen, scenario)
        screen._last_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render(f"Agents: {label}", img, 4.0)

    def device_status(self, screen: DeviceStatusScreen) -> str:
        _inject_mock_device_status(screen)
        screen._last_hash = None
        img = screen.render(self._display.width, self._display.height)
        return self._render("Device Status", img, 4.0)

    def ui_template(self, name: str) -> str:
        from ui.templates import render as tpl_render
        from ui.preview import MOCK_DATA

        data = MOCK_DATA.get(name, {"name": name})
        img = tpl_render(name, data)
        label = f"ui:{name}"
        return self._render(label, img, 3.0)

    def idle_screen(self) -> str:
        from ui.templates import render as tpl_render
        from ui.preview import MOCK_DATA

        img = tpl_render("idle", MOCK_DATA["idle"])
        return self._render("Idle", img, 3.0)

    def error_screen(self) -> str:
        from ui.templates import render as tpl_render
        from ui.preview import MOCK_DATA

        img = tpl_render("error", MOCK_DATA["error"])
        return self._render("Error", img, 3.0)

    @property
    def frames(self) -> List[str]:
        return list(self._frames)

    def make_gif(
        self, output_path: str = "out/demo_animation.gif", scale: int = 4
    ) -> str:
        from PIL import Image

        if not self._frames:
            raise RuntimeError("No frames to compose into GIF")

        images = []
        for path in self._frames:
            img = Image.open(path)
            resized = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
            images.append(resized.convert("RGB"))

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=800,
            loop=0,
        )
        return output_path

    def make_contact_sheet(
        self,
        output_path: str = "out/demo_contact_sheet.png",
        scale: int = 4,
    ) -> str:
        from PIL import Image, ImageDraw

        if not self._frames:
            raise RuntimeError("No frames to compose into contact sheet")

        images = []
        for path in self._frames:
            try:
                images.append(Image.open(path))
            except Exception:
                continue

        if not images:
            raise RuntimeError("No images to compose")

        cols = 4
        rows = (len(images) + cols - 1) // cols
        gap = 4
        label_h = 12

        sample_w, sample_h = images[0].size
        cell_w = sample_w * scale + gap
        cell_h = sample_h * scale + gap + label_h

        sheet_w = cols * cell_w + gap
        sheet_h = rows * cell_h + gap

        sheet = Image.new("1", (sheet_w, sheet_h), 255)
        draw = ImageDraw.Draw(sheet)

        for i, img in enumerate(images):
            col = i % cols
            row = i // cols
            x = gap + col * cell_w
            y = gap + row * cell_h

            resized = img.resize((sample_w * scale, sample_h * scale), Image.NEAREST)
            sheet.paste(resized, (x, y))

            basename = os.path.basename(self._frames[i]).replace(".png", "")
            parts = basename.split("_", 1)
            label = parts[1] if len(parts) > 1 else basename
            label_y = y + sample_h * scale + 1
            draw.text((x, label_y), label, fill=0)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        sheet.save(output_path, format="PNG")
        return output_path


def _run_demo(
    screens: List[Screen],
    display: DisplayBackend,
    cfg: AppConfig,
    fast: bool = False,
    include_ui: bool = False,
) -> DemoSequence:
    seq = DemoSequence(display, cfg, fast=fast)

    print("  === Boot Sequence ===")
    seq.boot()

    has_status = False
    has_tamagotchi = False
    has_agent_feed = False
    has_device_status = False

    for screen in screens:
        if isinstance(screen, StatusBoardScreen):
            has_status = True
            print("\n  === Status Board ===")
            seq.status_board_ok(screen)
            seq.status_board_degraded(screen)
            seq.status_board_down(screen)
            seq.status_board_recovered(screen)

        elif isinstance(screen, TamagotchiScreen):
            has_tamagotchi = True
            print("\n  === Tamagotchi ===")
            seq.tamagotchi_mood(screen, "ok", "Idle")
            seq.tamagotchi_mood(screen, "working", "Working")
            seq.tamagotchi_mood(screen, "error", "Error")
            seq.tamagotchi_mood(screen, "success", "Success")

        elif isinstance(screen, AgentFeedScreen):
            has_agent_feed = True
            print("\n  === Agent Feed ===")
            seq.agent_feed(screen, "hint", "Setup Hint")
            seq.agent_feed(screen, "idle", "Idle")
            seq.agent_feed(screen, "waiting", "Waiting")
            seq.agent_feed(screen, "mixed", "Working")

        elif isinstance(screen, DeviceStatusScreen):
            has_device_status = True
            print("\n  === Device Status ===")
            seq.device_status(screen)

    if not has_device_status:
        print("\n  === Device Status ===")
        ds = DeviceStatusScreen(ScreenConfig(name="Device", template="device_status"))
        _inject_mock_device_status(ds)
        ds.last_hash = None
        img = ds.render(display.width, display.height)
        seq._render("Device Status", img, 4.0)

    if include_ui or not (has_status or has_tamagotchi or has_agent_feed):
        print("\n  === UI Templates ===")
        for name in ["idle", "error"]:
            seq.ui_template(name)

    print("\n  === Closing ===")
    seq.idle_screen()

    return seq


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
        "demo", help="Full demo: boot, screen cycling, state animations, GIF output"
    )
    demo_parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip delays (instant render, still produces GIF)",
    )
    demo_parser.add_argument(
        "--all",
        action="store_true",
        help="Include all ui/ templates in demo sequence",
    )
    demo_parser.add_argument(
        "--contact-sheet",
        action="store_true",
        help="Generate a contact sheet grid of all demo frames",
    )
    demo_parser.add_argument(
        "--show",
        action="store_true",
        help="Open GIF and contact sheet in system viewer after completion",
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

    from core.logging_setup import setup_logging

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
        print(f"\n=== {APP_NAME.title()} Demo ===\n")
        if not getattr(args, "fast", False):
            print("  (use --fast to skip delays)\n")
        try:
            seq = _run_demo(
                screens,
                display,
                cfg=cfg,
                fast=getattr(args, "fast", False),
                include_ui=getattr(args, "all", False),
            )
        finally:
            display.close()

        gif_path = seq.make_gif()
        print(f"\n  Animation -> {gif_path}")

        open_paths = [gif_path]

        if getattr(args, "contact_sheet", False):
            cs_path = seq.make_contact_sheet()
            print(f"  Contact sheet -> {cs_path}")
            open_paths.append(cs_path)

        print(f"  {len(seq.frames)} frame(s) -> {seq._output_dir}/")

        if getattr(args, "show", False):
            _show_images(open_paths)

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
        import core

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
        import pisugar

        print(f"pisugar: {pisugar.__version__}")
    except ImportError:
        print("pisugar: NOT INSTALLED (pip install pisugar)")

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
