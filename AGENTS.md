# AGENTS.md - Guide for AI Agents Working on This Project

## Project Overview

This is a Python application for Raspberry Pi that drives a Waveshare 2.13" V3 e-paper display as a multi-screen AI status board and tamagotchi dashboard. It runs on Raspberry Pi OS Trixie (64-bit, Debian 13).

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

### The mock display backend

The default config (`config/providers.yaml`) uses `backend: mock` which renders to PNG files instead of e-paper. The waveshare backend is commented out:

```yaml
display:
  # backend: waveshare_2in13_v3   # Uncomment on Pi only
  backend: mock                     # Use this for development/testing
```

**Do NOT change the backend to `waveshare_2in13_v3`** - it will crash on non-Pi machines.

## Running the App (Non-Pi)

```bash
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
```

## Architecture

### Template System

Screens are defined in YAML config using templates. Two templates exist:

1. **`status_board`** - Category/bullet status display
   - Each category has a url, type (statuspage/json), icon, and items
   - `statuspage`: uses provider normalization (component name matching)
   - `json`: fetches raw JSON, maps item keys to statuses via convention (dot-notation via `resolve_key()`)
   - Items map upstream component keys to short display labels
   - Built-in icons: `anthropic`, `openai`, `lotus`, `generic`
   - Custom icons: pass a path to a 12x12 PNG file

2. **`tamagotchi`** - Character-based agent monitor
   - Single `url` returns JSON; all key access uses dot-notation via `resolve_key()`
   - Configurable sprites (idle/working/error/success) from PNG files
   - `mood_map` defines which JSON field drives sprite selection
   - `info_lines` define what data appears below the sprite
   - Supports simple key extraction and positional template strings (e.g. `+{0} M{1}` with `keys: [prs_created, prs_merged]`)

### Key Files

```
ai_health_board/
  config.py              # Data classes + YAML loading (ScreenConfig, StatusBoardCategory, etc.)
  input.py               # InputManager - PiSugar button signals (SIGUSR1/SIGUSR2), PID file
  screens/
    base.py              # Screen ABC (fetch, render, poll_interval, display_duration, has_changed)
    status_board.py      # Status board template + pixel art icon generators
    tamagotchi.py         # Tamagotchi template (config-driven sprites, mood_map, info_lines)
  display/
    base.py              # DisplayBackend ABC (render, render_image, flush, close)
    mock_png.py          # PNG file output (for development)
    waveshare_2in13.py   # V3 e-paper driver (Pi only, partial refresh)
  providers/
    base.py              # StatusProvider ABC
    statuspage.py        # Atlassian Statuspage adapter
  scheduler.py           # Async screen-cycling loop with input interruption
  models.py              # ServiceStatus, ComponentStatus, ProviderStatus, AppState
app.py                   # CLI entrypoint (run, once, preview, demo, doctor)
config/providers.yaml    # Active config (mock backend)
```

### PiSugar Button Integration

The PiSugar S battery has a physical button connected to **GPIO3 (pin 5)**. A standalone button daemon reads GPIO3 directly via `gpiozero` -- no I2C or `pisugar-server` required.

| Button | Action |
|---|---|
| Short press (< 1.2s) | Next screen (sends SIGUSR1 to lotus-companion) |
| Long press (>= 1.2s) | Shutdown screen + `sudo shutdown -h now` |

Files:
- `scripts/pisugar_button.py` - Button daemon (gpiozero, GPIO3, pull-up, debounce)
- `systemd/pisugar-button.service` - Systemd service

How it works:
1. `pisugar_button.py` runs as a separate daemon, listening on GPIO3 via gpiozero
2. On short press, it reads `/tmp/lotus-companion.pid` and sends SIGUSR1 to the main app
3. On long press, it attempts a shutdown screen update, then runs `sudo shutdown -h now`
4. The main app's `InputManager` receives SIGUSR1 and interrupts the scheduler to switch screens

Important (on Pi):
- **Disable I2C** if `pisugar-server` is running -- it can interfere with GPIO3
- **Set `GPIOZERO_PIN_FACTORY=lgpio`** (required on Trixie)
- Install: `sudo apt install python3-gpiozero python3-lgpio`

Installing the button daemon:
```bash
sudo ./scripts/install_services.sh
```

This script detects your repo path and username, generates both service files with correct absolute paths, and deploys them. Re-run after `git pull` to update paths.

View logs: `sudo journalctl -u pisugar-button -f`

Testing without PiSugar hardware: `kill -USR1 $(cat /tmp/lotus-companion.pid)` works on any Linux.

### Display Dimensions

- Waveshare 2.13" V3 e-paper: **122 x 250 pixels** (portrait, no rotation)
- Images are created in PIL mode `'1'` (1-bit black/white)
- `fill=255` for white, `fill=0` for black

### Partial Refresh

The V3 e-paper supports partial refresh (`displayPartial()`) for fast, flicker-free updates. Full refresh (`displayPartBaseImage()`) only happens on:
- First render (base image not yet set)
- Every 50 updates (ghosting cleanup)

The scheduler always renders when switching screens. `has_changed()` only gates re-renders of the same screen.

## Testing

```bash
python -m pytest tests/ -v
```

All 78 tests should pass. Tests cover:
- Config loading and data classes
- Screen rendering (status board + tamagotchi)
- Provider normalization (statuspage)
- Pixel art icon generation
- Mood resolution and info line formatting
- Mock data injection for demo mode
- InputManager (PID file, signal handling, interruptible sleep)

## Config Format

See `config/providers.yaml.example` for the full annotated config with both templates.

## Pi-Specific Setup (For Reference Only)

Do NOT attempt these on your machine:
- `sudo apt install python3-lgpio python3-spidev`
- `export GPIOZERO_PIN_FACTORY=lgpio`
- Waveshare driver install via `setup.py`
- `sudo raspi-config` to enable SPI

These are documented in the README for when deploying to the actual Pi.
