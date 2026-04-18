# AI Health Status Board

A Python appliance for Raspberry Pi that polls AI service status endpoints and renders a dashboard on a 2.13" e-paper display.

## What it does

- Polls public status endpoints (Atlassian Statuspage) every 5 minutes
- Renders a monochrome dashboard on a Waveshare 2.13" V3 e-paper display
- Shows per-component status: OK / DEGRADED / DOWN / UNKNOWN
- Retains last known state on fetch failures (marked STALE)
- Runs as a systemd service with auto-restart

## Supported hardware

| Hardware | Notes |
|----------|-------|
| Raspberry Pi Zero 2 W, Pi 3, Pi 4, Pi 5 | With SPI enabled |
| Waveshare 2.13" V3 e-paper (black/white) | 122x250 pixels, SPI interface |
| Any laptop | Mock mode outputs PNG files |

## Quick start: laptop (mock mode)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/providers.yaml.example config/providers.yaml
python app.py preview
# See: ./out/frame.png
```

## Fresh Raspberry Pi setup

Tested on Raspberry Pi OS Trixie (64-bit, Debian 13).

### Step 1: System packages

```bash
sudo apt update
sudo apt install -y python3-lgpio python3-spidev python3-rpi.gpio python3-pip python3-setuptools python3-venv
```

`python3-lgpio` is required on Trixie/Bookworm. These releases replaced the deprecated `/sys/class/gpio` sysfs interface with the character device `/dev/gpiochip*`. Without `lgpio`, gpiozero falls back to `NativeFactory` which crashes on pin export.

### Step 2: Enable SPI

```bash
sudo raspi-config
# Interface Options -> SPI -> Enable -> Finish -> Reboot
```

Verify after reboot:
```bash
ls /dev/spidev0.0 /dev/spidev0.1
```

### Step 3: Install Waveshare e-paper driver

The Waveshare driver is not on PyPI. Install it from their GitHub repo:

```bash
cd ~
git clone https://github.com/waveshareteam/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install
```

Verify:
```bash
python3 -c "from waveshare_epd import epd2in13_V3; print('OK')"
```

### Step 4: Add user to GPIO/SPI groups

```bash
sudo usermod -a -G spi,gpio $USER
```

Log out and back in for group changes to take effect.

### Step 5: Deploy the application

From your development machine:
```bash
scp -r ai-health-board pi@raspberrypi.local:~/
```

On the Pi:
```bash
cd ~/ai-health-board

# venv MUST include --system-site-packages to access lgpio, spidev, waveshare_epd
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Configure for e-paper display

```bash
cp config/providers.yaml.example config/providers.yaml
```

Edit `config/providers.yaml` and change the display backend:

```yaml
display:
  backend: waveshare_2in13_v3  # was: mock
```

The `width: 122` and `height: 250` values match the EPD's native portrait resolution. The driver auto-rotates landscape images. Leave them as-is.

### Step 7: Set GPIO pin factory

Required on Trixie/Bookworm so gpiozero uses `lgpio`:

```bash
export GPIOZERO_PIN_FACTORY=lgpio
echo 'export GPIOZERO_PIN_FACTORY=lgpio' >> ~/.bashrc
```

### Step 8: Test

```bash
source venv/bin/activate
export GPIOZERO_PIN_FACTORY=lgpio
python app.py once
```

You should see the e-paper display update with the status dashboard.

### Step 9: Install as systemd service

Edit `systemd/ai-health-board.service` if your username or path differs from `pi` / `/home/pi/ai-health-board`.

```bash
sudo cp systemd/ai-health-board.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-health-board
sudo systemctl start ai-health-board
```

The service file already sets `GPIOZERO_PIN_FACTORY=lgpio`.

View logs:
```bash
sudo journalctl -u ai-health-board -f
```

Stop/restart:
```bash
sudo systemctl stop ai-health-board
sudo systemctl restart ai-health-board
```

## CLI reference

```bash
python app.py doctor                       # Check environment and dependencies
python app.py preview                      # Render to PNG (mock mode, no hardware)
python app.py once                         # Fetch + render once, then exit
python app.py run                          # Long-running poll loop
python app.py run --once-after 30          # Wait 30s before first refresh
```

## Configuration

All configuration is in `config/providers.yaml`.

```yaml
refresh_seconds: 300              # Poll interval (default: 300 = 5 min)
timezone: UTC                     # Timestamp timezone

display:
  backend: waveshare_2in13_v3     # "mock" or "waveshare_2in13_v3"
  width: 122                      # EPD native portrait width
  height: 250                     # EPD native portrait height
  full_refresh_every_n_updates: 6 # Full refresh to reduce ghosting

providers:
  - name: Claude
    type: statuspage
    url: https://status.claude.com/api/v2/summary.json
    components:
      - claude.ai
      - Claude Code
      - Claude API (api.anthropic.com)

  - name: OpenAI
    type: statuspage
    url: https://status.openai.com/api/v2/summary.json
    components:
      - App
      - Conversations
      - Codex Web
      - Codex API
```

Component name matching:
1. Exact match
2. Case-insensitive fallback
3. Not found -> UNKNOWN (logged as warning)

## Adding a new provider adapter

1. Create `ai_health_board/providers/custom.py`
2. Implement `StatusProvider` base class with `__init__(display_name, url, component_keys)`
3. Register in `ai_health_board/providers/__init__.py` `_BACKENDS` dict
4. Add entries to `config/providers.yaml` with `type: custom`

Example:

```python
from ai_health_board.providers.base import StatusProvider, ServiceStatus
from typing import Any, Dict

class CustomProvider(StatusProvider):
    def __init__(self, display_name: str, url: str, component_keys: list):
        self._display_name = display_name
        self.url = url
        self.component_keys = component_keys

    def provider_type(self) -> str:
        return "custom"

    def display_name(self) -> str:
        return self._display_name

    async def fetch_status(self, session, timeout=10) -> Dict[str, Any]:
        import aiohttp
        resp = await session.get(self.url, timeout=aiohttp.ClientTimeout(total=timeout))
        resp.raise_for_status()
        return await resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, ServiceStatus]:
        return {"service_name": ServiceStatus.OK}
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'lgpio'`

```bash
sudo apt install python3-lgpio
```

### `PinFactoryFallback: Falling back from lgpio`

Set the environment variable:
```bash
export GPIOZERO_PIN_FACTORY=lgpio
```

### `OSError: [Errno 22] Invalid argument` on `/sys/class/gpio`

You are on Trixie/Bookworm which removed the sysfs GPIO interface. Set:
```bash
export GPIOZERO_PIN_FACTORY=lgpio
```

### `KeyError: 24` or `FileNotFoundError: /sys/class/gpio/gpio24/value`

Same root cause as above. The sysfs GPIO interface is gone on Trixie. Install `python3-lgpio` and set `GPIOZERO_PIN_FACTORY=lgpio`.

### Display not updating

Check in order:
```bash
# 1. SPI enabled?
ls /dev/spidev0.0

# 2. Waveshare V3 driver installed?
python3 -c "from waveshare_epd import epd2in13_V3; print('OK')"

# 3. GPIO pin factory set?
echo $GPIOZERO_PIN_FACTORY   # should print: lgpio

# 4. Config backend correct?
grep backend config/providers.yaml   # should be: waveshare_2in13_v3

# 5. User in correct groups?
groups   # should include spi and gpio

# 6. Test with mock first:
#    Set backend: mock in config, then: python app.py preview
```

### venv can't find lgpio / spidev / waveshare_epd

The venv was created without `--system-site-packages`. These packages are installed at the system level via `apt` or `sudo python3 setup.py install`. The venv needs access to them.

Fix:
```bash
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'setuptools'` (during waveshare install)

```bash
sudo apt install python3-setuptools
```

### OpenAI components showing UNKNOWN

Component names must match the upstream Statuspage. As of 2026, OpenAI uses these names:
- `App` (not "ChatGPT")
- `Conversations` (not "API")
- `Codex Web`
- `Codex API`

Run this to see current names:
```bash
curl -s https://status.openai.com/api/v2/summary.json | python3 -c "import json,sys; [print(f'  {c[\"name\"]}') for c in json.load(sys.stdin)['components']]"
```

## Security notes

- Outbound-only HTTP polling -- no inbound network services
- No secrets or API keys required for public status endpoints
- SSH keys recommended for deployment
- Runs as unprivileged user (must be in `spi` and `gpio` groups)
- No database, no web framework

## Development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

## License

MIT License
