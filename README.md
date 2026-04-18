# AI Health Status Board

A small Python application for Raspberry Pi that displays AI service status on an e-paper display.

## What it does

Polls public health/status endpoints for AI services and renders a clean status dashboard on a 2.13" e-paper display (Waveshare-compatible). Supports easy extension via YAML configuration and a plugin adapter architecture.

## Supported hardware

- Raspberry Pi Zero / Pi Zero 2 W (or any Pi with SPI)
- 2.13" e-paper display (Waveshare black/white panel, SPI)
- Mock PNG backend for testing on laptops (no hardware required)

## Dependencies

- Python 3.11+
- `aiohttp` - Async HTTP client
- `pillow` - Image rendering
- `pyyaml` - Configuration parsing
- `waveshare_epd` - E-paper driver (install manually, see below)

## Quick start on Raspberry Pi

### 1. Copy the repository to your Pi

```bash
# From your development machine
scp -r ai-health-board pi@raspberrypi.local:~/
ssh pi@raspberrypi.local
```

### 2. Enable SPI interface

```bash
sudo raspi-config
# -> Interface Options -> SPI -> Enable -> Finish -> Reboot
```

### 3. Install the application

```bash
cd ~/ai-health-board
./scripts/install.sh
```

This will:
- Create a Python virtual environment
- Install dependencies (aiohttp, pillow, pyyaml)
- Copy example configuration
- Run doctor check to verify environment

### 4. Install Waveshare e-paper driver (for hardware display)

```bash
cd ~
git clone https://github.com/waveshareteam/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install
```

### 5. Configure for your display

Edit `config/providers.yaml`:

```yaml
# For mock/PNG testing (no hardware needed)
display:
  backend: mock

# For actual e-paper display
display:
  backend: waveshare_2in13
  width: 250
  height: 122
  rotation: 0
```

### 6. Test the installation

```bash
# Test in mock mode (generates out/frame.png)
source venv/bin/activate
python app.py preview

# Test with actual display (requires waveshare_epd)
python app.py once
```

### 7. Install as systemd service

Edit `systemd/ai-health-board.service` if your username is not `pi` or if you installed to a different path:

```ini
User=yourusername
WorkingDirectory=/home/yourusername/ai-health-board
ExecStart=/home/yourusername/ai-health-board/venv/bin/python ...
```

Then install:

```bash
sudo cp systemd/ai-health-board.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-health-board
sudo systemctl start ai-health-board
```

View logs:
```bash
sudo journalctl -u ai-health-board -f
```

## Running in mock mode on a laptop

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/providers.yaml.example config/providers.yaml

# Ensure mock backend is selected in config
grep "backend:" config/providers.yaml  # should show 'backend: mock'

python app.py preview
# Output: ./out/frame.png
```

## Configuring providers

Edit `config/providers.yaml`:

```yaml
refresh_seconds: 300
timezone: UTC
display:
  backend: waveshare_2in13
  width: 250
  height: 122
  rotation: 0
  full_refresh_every_n_updates: 6

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
      - ChatGPT
      - API
      - Codex Web
      - Codex API
```

Matching is resilient:
1. Exact match first
2. Case-insensitive fallback
3. If not found -> UNKNOWN (logged as warning)

## Adding a new provider adapter

1. Create a new file in `ai_health_board/providers/` (e.g., `custom.py`)
2. Implement the `StatusProvider` base class
3. Register it in `ai_health_board/providers/__init__.py`
4. Add entries to your `config/providers.yaml`

Example adapter:

```python
from ai_health_board.providers.base import StatusProvider, ServiceStatus
from ai_health_board.models import ComponentStatus
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

    async def fetch_status(self, session) -> Dict[str, Any]:
        # Fetch from your custom endpoint
        resp = await session.get(self.url, timeout=10)
        return await resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, ServiceStatus]:
        # Map your API response to ServiceStatus
        return {"service_name": ServiceStatus.OK}
```

Then register in `ai_health_board/providers/__init__.py`:

```python
_BACKENDS = {
    "statuspage": "...",
    "custom": "ai_health_board.providers.custom.CustomProvider",
}
```

## CLI Commands

```bash
python app.py doctor        # Check environment and dependencies
python app.py preview       # Render one frame to PNG (mock mode)
python app.py once          # Fetch and display once, then exit
python app.py run           # Long-running service loop
python app.py run --once-after 30  # Wait 30s before first refresh
```

## Troubleshooting

### Doctor check fails

Run `./scripts/doctor.sh` to diagnose:

```bash
./scripts/doctor.sh
```

Common issues:
- **SPI not enabled**: Run `sudo raspi-config`, enable SPI, reboot
- **waveshare_epd missing**: Install from Waveshare's GitHub repo
- **Missing dependencies**: Run `./scripts/install.sh`

### Display not updating

1. Check SPI is enabled: `ls /dev/spidev*`
2. Check waveshare_epd is installed: `python3 -c "from waveshare_epd import epd2in13"`
3. Check logs: `sudo journalctl -u ai-health-board -f`
4. Try mock mode first: set `backend: mock` in config, run `python app.py preview`

### HTTP fetch failures

- Network connectivity: `ping status.claude.com`
- Upstream outage: Check status pages in browser
- Stale data: App retains last known state and marks as stale

### Partial refresh issues

E-paper displays ghost over time. The app performs a full refresh every N cycles (configurable via `full_refresh_every_n_updates` in display config).

## Security notes

- Outbound-only HTTP polling (no inbound services required)
- No secrets required for public status endpoints
- SSH keys recommended for scp/deployment
- Runs as unprivileged user by default
- No database or web framework - minimal attack surface

## Development

Run tests:
```bash
python -m pytest tests/ -v
```

## License

MIT License - Internal use only.
