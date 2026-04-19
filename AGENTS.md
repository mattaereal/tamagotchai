# AGENTS.md - Guide for AI Agents Working on This Project

## Project Overview

Tamagotchai is a Python application for Raspberry Pi that drives Waveshare 2.13" e-paper displays as a multi-screen AI status board and tamagotchi dashboard. It runs on Raspberry Pi OS Trixie (64-bit, Debian 13).

## Critical: Development Environment vs Target Device

**You are likely NOT running on a Raspberry Pi.** The hardware-specific dependencies below will NOT be available on your machine. This is expected and accounted for.

### What won't work on your machine:
- `waveshare_epd` (e-paper display driver) - requires SPI + GPIO hardware
- `lgpio` (GPIO library) - requires Pi hardware
- `/dev/spidev*` devices - require Pi SPI interface
- Actual e-paper display output

### What DOES work on your machine:
- All Python code execution and testing
- The `mock` display backend (renders to PNG files in `out/`)
- Unit tests (`python -m pytest tests/`)
- Config loading and validation
- Screen rendering logic (generates PIL Images)
- The `demo` command with mock data
- The `init` setup wizard

### The mock display backend

The default config (`config/display.yml`) uses `backend: mock` which renders to PNG files instead of e-paper.

**Do NOT change the backend to any `waveshare_*` value** - it will crash on non-Pi machines.

## Running the App (Non-Pi)

```bash
# Interactive setup
python app.py init

# Run tests
python -m pytest tests/ -v

# Render with mock data (no network needed)
python app.py demo

# Animate status changes (partial refresh test)
python app.py demo --animate

# Preview current state
python app.py preview

# Doctor check (will show SPI/GPIO as missing - this is fine)
python app.py doctor

# Preview all ui/ templates
python app.py ui-preview
```

## Architecture

### Configuration

Config is split across three files in `config/`:

| File | Purpose |
|---|---|
| `display.yml` | Display hardware (backend, resolution, refresh settings) |
| `tamagotchai.yml` | App-level settings (refresh interval, timezone) |
| `screens.yml` | Screen definitions (status boards, tamagotchis) |

Loading merges all three. Each file is optional -- defaults are used for any missing file. The `python app.py init` wizard generates all three interactively.

### Template System

Screens are defined in YAML config using templates:

1. **`status_board`** - Category/bullet status display
   - Each category has a url, type (statuspage/json), icon, and items
   - `statuspage`: uses provider normalization (component name matching)
   - `json`: fetches raw JSON, maps item keys to statuses via convention (dot-notation via `resolve_key()`)
   - Built-in icons: `anthropic`, `openai`, `lotus`, `generic`
   - Custom icons: pass a path to a 12x12 PNG file

2. **`tamagotchi`** - Character-based agent monitor
   - Single `url` returns JSON; all key access uses dot-notation via `resolve_key()`
   - Configurable sprites (idle/working/error/success) from PNG files
   - `mood_map` defines which JSON field drives sprite selection
   - `info_lines` define what data appears below the sprite

3. **`ui:<name>`** - Any registered ui/ template (boot, setup, idle, error, message, etc.)
   - Wrapped as `UiTemplateScreen` for the scheduler
   - Can also use bare name (e.g. `template: idle`) if it matches a ui/ template

### Display Backends

All 2.13" Waveshare variants are supported:

| Backend | Display | Resolution | Partial refresh |
|---|---|---|---|
| `mock` | PNG file output | 122x250 | N/A |
| `waveshare_2in13_v1` | V1 (B/W) | 122x250 | Yes (LUT swap) |
| `waveshare_2in13_v2` | V2 (B/W) | 122x250 | Yes |
| `waveshare_2in13_v3` | V3 (B/W) | 122x250 | Yes |
| `waveshare_2in13_v4` | V4 (B/W, fast refresh) | 122x250 | Yes |
| `waveshare_2in13bc` | BC (B/W/R, 104x212) | 104x212 | No |
| `waveshare_2in13b_v3` | B V3 (B/W/R) | 122x250 | No |
| `waveshare_2in13b_v4` | B V4 (B/W/R) | 122x250 | No |
| `waveshare_2in13d` | D (B/W, flexible, 104x212) | 104x212 | Yes |
| `waveshare_2in13g` | G (4-color) | 122x250 | No |

Width/height are auto-set from the backend profile in `DISPLAY_PROFILES` (defined in `config.py`).

### Key Files

```
ai_health_board/
  config.py              # Data classes + YAML loading (3-file config, DISPLAY_PROFILES)
  input.py               # InputManager - PiSugar button signals (SIGUSR1/SIGUSR2), PID file
  wifi_display_hook.py   # Display hook for wifi onboarding (renders setup info on e-paper)
  screens/
    base.py              # Screen ABC (fetch, render, poll_interval, display_duration, has_changed)
    status_board.py      # Status board template + pixel art icon generators
    tamagotchi.py         # Tamagotchi template (config-driven sprites, mood_map, info_lines)
    ui_template.py       # UiTemplateScreen - wraps ui/ templates as Screen instances
  display/
    base.py              # DisplayBackend ABC (render, render_image, flush, close)
    mock_png.py          # PNG file output (for development)
    waveshare_2in13_v1.py   # V1 driver (LUT swap partial refresh)
    waveshare_2in13_v2.py   # V2 driver (displayPartial)
    waveshare_2in13_v3.py   # V3 driver (displayPartial)
    waveshare_2in13_v4.py   # V4 driver (displayPartial + fast refresh)
    waveshare_2in13bc.py    # BC driver (B/W/R, full refresh only)
    waveshare_2in13b_v3.py  # B V3 driver (B/W/R, full refresh only)
    waveshare_2in13b_v4.py  # B V4 driver (B/W/R, full refresh only)
    waveshare_2in13d.py     # D driver (B/W, flexible)
    waveshare_2in13g.py     # G driver (4-color, full refresh only)
  providers/
    base.py              # StatusProvider ABC
    statuspage.py        # Atlassian Statuspage adapter
  scheduler.py           # Async screen-cycling loop with input interruption
  models.py              # ServiceStatus, ComponentStatus, ProviderStatus, AppState
ui/
  canvas.py              # Core rendering surface (PIL 1-bit wrapper)
  layout.py              # Layout primitives (header, item_row, footer, etc.)
  fonts.py               # Font loading (PIL default bitmap, TTF-ready)
  assets/__init__.py     # Pixel art icons (anthropic, openai, lotus, generic) + sprite loader
  templates/             # Template registry + 7 screen templates
  image_tools/           # Image preparation pipeline + dithering
  preview/               # Template preview renderer + contact sheet
commands/
  init.py                # Interactive setup wizard
app.py                   # CLI entrypoint (init, run, once, preview, demo, doctor, ui-preview)
config/
  display.yml            # Display hardware config
  tamagotchai.yml        # App-level settings
  screens.yml            # Screen definitions
  *.example              # Annotated example configs
wifi/                    # Wi-Fi onboarding subsystem (self-contained)
scripts/
  install.sh             # Full installer (venv + deps + init wizard)
  install_services.sh    # Systemd service generator
  pisugar_button.py      # PiSugar S button daemon (GPIO3)
  doctor.sh              # Shell-based doctor check
  run_once.sh            # One-shot run helper
  prepare_image.py       # Image preparation CLI
  preview_all.py         # Template preview CLI
systemd/
  tamagotchai.service    # Main app service template
  pisugar-button.service # Button daemon service template
```

### PiSugar Button Integration

The PiSugar S battery has a physical button connected to **GPIO3 (pin 5)**. A standalone button daemon reads GPIO3 directly via `gpiozero`.

| Button | Action |
|---|---|
| Short press (< 1.2s) | Next screen (sends SIGUSR1 to tamagotchai) |
| Long press (>= 1.2s) | Shutdown screen + `sudo shutdown -h now` |

How it works:
1. `pisugar_button.py` runs as a separate daemon, listening on GPIO3 via gpiozero
2. On short press, it reads `/tmp/tamagotchai.pid` and sends SIGUSR1 to the main app
3. On long press, it attempts a shutdown screen update, then runs `sudo shutdown -h now`
4. The main app's `InputManager` receives SIGUSR1 and interrupts the scheduler to switch screens

Testing without PiSugar hardware: `kill -USR1 $(cat /tmp/tamagotchai.pid)` works on any Linux.

### Display Dimensions

- Waveshare 2.13" V1-V4 e-paper: **122 x 250 pixels** (portrait, no rotation)
- Waveshare 2.13" BC/D: **104 x 212 pixels**
- Images are created in PIL mode `'1'` (1-bit black/white)
- `fill=255` for white, `fill=0` for black

### Partial Refresh

V2/V3/V4/D e-papers support partial refresh (`displayPartial()`) for fast, flicker-free updates. Full refresh (`displayPartBaseImage()`) only happens on:
- First render (base image not yet set)
- Every N updates (ghosting cleanup, configurable via `full_refresh_every_n_updates`)

V1 uses a different API: `init(PART_UPDATE)` + `display()` instead of `displayPartial()`.

3-color (BC, B V3, B V4) and 4-color (G) displays do NOT support partial refresh.

## Testing

```bash
python -m pytest tests/ -v
```

Tests are split into:
- `test_layout.py` - Layout, canvas, fonts, assets
- `test_new_modules.py` - Core modules (config, screens, providers, input)
- `test_ui_layout.py` - UI canvas, layout, fonts, assets
- `test_ui_templates.py` - UI templates, preview, UiTemplateScreen integration
- `test_ui_image_tools.py` - Image tools, dithering, presets

The `wifi/` subsystem has its own Flask app and tests -- it is self-contained.

## Config Format

See `config/*.example` files for annotated examples:
- `config/display.yml.example` - Display hardware
- `config/tamagotchai.yml.example` - App settings
- `config/screens.yml.example` - Screen definitions

## Pi-Specific Setup (For Reference Only)

Do NOT attempt these on your machine:
- `sudo apt install python3-lgpio python3-spidev`
- `export GPIOZERO_PIN_FACTORY=lgpio`
- Waveshare driver install via `setup.py`
- `sudo raspi-config` to enable SPI

These are documented in the README for when deploying to the actual Pi.
