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

# Full demo with boot sequence, animations, and GIF output
python app.py demo

# Fast demo (skip delays, still produces GIF)
python app.py demo --fast

# Preview current state
python app.py preview

# Doctor check (will show SPI/GPIO as missing - this is fine)
python app.py doctor

# Preview all ui/ templates
python app.py ui-preview
```

## Architecture

### Package Structure

The project is organized into top-level packages with clear separation of concerns:

| Package | Purpose | Depends on |
|---|---|---|
| `core/` | App runtime: config, display drivers, providers, screen data-fetching, scheduler | `ui/` (templates only, for render delegation) |
| `ui/` | All rendering: canvas, layout, templates, assets, image tools | Nothing (zero inbound deps) |
| `commands/` | CLI commands (init wizard) | `core/` (config) |
| `config/` | YAML configuration files | N/A (data only) |
| `wifi/` | WiFi onboarding subsystem (self-contained Flask app) | Nothing at import time |

Dependency flow: `ui/` (leaf) <- `core/` <- `commands/` <- `app.py` (root)

`core/screens/` delegates all pixel rendering to `ui/templates/`. Each screen's `render()` method converts its internal data to a plain dict and calls a registered template function. This keeps all Canvas/layout/assets usage inside `ui/` and all data-fetching/config logic inside `core/`.

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
   - `stale_threshold` (seconds, default 120): if `last_heartbeat` is older than this, status is overwritten to `"offline"`

3. **`agent_feed`** - Multi-agent compact list
   - Reads multiple agent URLs in parallel (`agents` list in config)
   - Each agent serves the Standard Agent Status JSON (see below)
   - Renders a compact row per agent: icon + name + status + message
   - When `metadata` includes `model`, `tokens_total`/`tokens_input`/`tokens_output`, or `cost_usd`, renders a compact metadata line (e.g. `claude-3.7  $0.004`)
   - Applies stale detection per-agent using `stale_threshold`
   - Status icons: `[+]` idle/ok, `[!]` working/waiting_input, `[-]` error/stuck/offline, `[*]` success

4. **`device_status`** - Local device vitals
   - Shows hostname, IP, SSID, BSSID, WiFi status, signal, CPU temp, memory, disk, uptime, battery, PID, version
   - No URL needed -- gathers data from local system calls (stdlib + subprocess)
   - Battery reads from PiSugar (requires `pisugar` pip package on Pi)

5. **`ui:<name>`** - Any registered ui/ template (boot, setup, idle, error, message, etc.)
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
core/
  config.py              # Data classes + YAML loading (3-file config, DISPLAY_PROFILES)
  input.py               # InputManager - PiSugar button signals (SIGUSR1/SIGUSR2), PID file
  wifi_display_hook.py   # Display hook for wifi onboarding (renders setup info on e-paper)
  models.py              # ServiceStatus, ComponentStatus, ProviderStatus, AppState
  cache.py               # Cache load/save for provider results
  logging_setup.py       # Logging configuration
  scheduler.py           # Async screen-cycling loop with input interruption
  screens/
    base.py              # Screen ABC (fetch, render, poll_interval, display_duration, has_changed)
    status_board.py      # Status board screen (fetch + render delegates to ui/templates/status_board)
    tamagotchi.py        # Tamagotchi screen (fetch + mood resolve, render delegates to ui/templates/tamagotchi)
    agent_feed.py        # Agent feed screen (fetch, render delegates to ui/templates/agent_feed)
    device_status.py     # Device status screen (local system calls, render delegates to ui/templates/device_status)
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
ui/
  canvas.py              # Core rendering surface (PIL 1-bit wrapper)
  layout.py              # Layout primitives (header, item_row, footer, etc.)
  fonts.py               # Font loading (PIL default bitmap, TTF-ready)
  assets/__init__.py     # Pixel art icons (anthropic, openai, lotus, generic) + sprite loader
  templates/             # Template registry + 11 screen templates
    boot.py              # Boot/splash screen
    setup.py             # WiFi setup instructions
    status_dashboard.py  # Generic status dashboard (preview)
    status_board.py      # Live status board rendering (used by core/screens/status_board.py)
    tamagotchi.py        # Live tamagotchi rendering (used by core/screens/tamagotchi.py)
    agent_feed.py        # Live agent feed rendering (used by core/screens/agent_feed.py)
    device_status.py     # Device vitals rendering (used by core/screens/device_status.py)
    detail.py            # Single service detail view
    message.py           # Alert/notification screen
    idle.py              # Idle/mascot screen
    error.py             # Error/offline screen
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

### Mood Map (Extended)

The `mood_map` config has two modes:

**Legacy** (binary ok/error):
```yaml
mood_map:
  key: status
  ok: idle
  ok_busy: working
  error: error
```
If `status == "ok"` and `pending > 0`, uses `ok_busy`; if `pending == 0`, uses `ok`; anything else uses `error`.

**Explicit map** (recommended for agents):
```yaml
mood_map:
  key: status
  map:
    idle: idle
    working: working
    waiting_input: working
    stuck: error
    error: error
    success: success
    offline: error
  fallback: idle
```
When `map` is present, it takes precedence. The JSON field value is looked up in `map`; if not found, `fallback` is used. This supports arbitrary agent status strings.

### Stale / Offline Detection

Both `tamagotchi` and `agent_feed` screens support stale detection via `stale_threshold` (default: 120 seconds). After fetching JSON, if `last_heartbeat` is older than `stale_threshold` seconds, the agent's `status` is overwritten to `"offline"` and mood is re-resolved. This allows mood maps to render a distinct offline state.

If the fetch itself fails (connection refused, timeout), `__fetch_error` is set and the screen shows `[-] connection error`.

### Standard Agent Status JSON

Any AI agent can feed its live status into the display by serving this JSON at an HTTP endpoint (e.g. `http://agent-host:7788/status`):

```json
{
  "status": "working",
  "message": "cmd: git commit",
  "pending": 1,
  "last_heartbeat": "2026-04-19T10:35:22Z",
  "metadata": {
    "project": "tamagotchai",
    "model": "anthropic/claude-3.7-sonnet",
    "tokens_input": 1240,
    "tokens_output": 340,
    "tokens_total": 1580,
    "cost_usd": 0.0042,
    "tool_name": "bash",
    "message_count": 5,
    "files_modified": 3,
    "session_duration_ms": 245000
  }
}
```

**For OpenCode users:** Instead of building a custom endpoint, install `plugins/opencode-plugin-tamagotchai/` as an OpenCode plugin. It starts an HTTP server inside the OpenCode process and serves this exact JSON schema automatically, tracking sessions, tools, tokens, model, cost, files modified, and more from internal events. See the plugin README for setup.

### Default shipped screen

Tamagotchai ships with `agent_feed` as its default screen, polling `http://127.0.0.1:7788/status` for an OpenCode agent. If the agent is offline, the display shows setup instructions instead of a cryptic error -- telling the user exactly how to install the plugin and start the agent.

### Agent Status JSON fields

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | Yes | One of: `idle`, `working`, `waiting_input`, `stuck`, `error`, `success` |
| `last_heartbeat` | ISO 8601 | Yes | Timestamp of last update; used for stale/offline detection |
| `message` | string | No | Current activity description (shown in agent_feed and info_lines) |
| `pending` | int | No | Number of pending tasks |
| `metadata` | object | No | Freeform dict; accessible via dot-notation in info_lines |

**Common metadata keys** (populated by `opencode-plugin-tamagotchai`):

| Key | Description | Displayed by `agent_feed`? |
|---|---|---|
| `model` | Active LLM model | Yes (truncated) |
| `tokens_input` / `tokens_output` / `tokens_total` | Token usage counters | Yes (compact format) |
| `cost_usd` | Cumulative cost in USD | Yes |
| `tool_name` | Last tool/command used | Yes (in `message`) |
| `project` | Project name | Yes (fallback) |
| `message_count` | Messages this session | Yes (fallback) |
| `files_modified` | Unique files touched | Yes (fallback) |
| `session_duration_ms` | Session elapsed time | No (available in JSON) |
| `commits` / `lines_added` / `lines_removed` | Git diff stats | No (available in JSON) |

## Testing

```bash
python -m pytest tests/ -v
```

Tests are split into:
- `test_config.py` - Config loading and validation
- `test_input.py` - InputManager, signal handling, debounce
- `test_layout.py` - Layout, canvas, fonts, assets (core screens)
- `test_new_modules.py` - Core modules (config, screens, providers, input, device_status)
- `test_statuspage_provider.py` - Statuspage provider
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
