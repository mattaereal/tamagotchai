#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== AI Health Board – Doctor ==="
echo ""

ERRORS=0
WARNINGS=0

# Check Python version
echo -n "Python: "
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "$PYTHON_VERSION"

# Check if venv exists
if [[ -d "venv" ]]; then
    echo "Virtual environment: EXISTS"
else
    echo "Virtual environment: MISSING (run ./scripts/install.sh first)"
    ((ERRORS++))
fi

# Check config
if [[ -f "config/providers.yaml" ]]; then
    echo "Config: EXISTS"
else
    echo "Config: MISSING (copy from config/providers.yaml.example)"
    ((WARNINGS++))
fi

# Check imports
echo -n "Core imports: "
if python3 -c "import ai_health_board, ai_health_board.config, ai_health_board.models, ai_health_board.providers, ai_health_board.display" 2>/dev/null; then
    echo "OK"
else
    echo "FAIL"
    ((ERRORS++))
fi

# Check aiohttp (critical)
echo -n "aiohttp: "
if python3 -c "import aiohttp; print(aiohttp.__version__)" 2>/dev/null; then
    : # version printed above
else
    echo "MISSING (install with: pip install aiohttp)"
    ((ERRORS++))
fi

# Check optional dependencies
echo -n "Pillow: "
if python3 -c "from PIL import Image; print('OK')" 2>/dev/null; then
    echo "OK"
else
    echo "MISSING"
    ((ERRORS++))
fi

echo -n "PyYAML: "
if python3 -c "import yaml; print('OK')" 2>/dev/null; then
    echo "OK"
else
    echo "MISSING"
    ((ERRORS++))
fi

# Check SPI devices
echo ""
echo "SPI devices:"
SPI_FOUND=false
for dev in /dev/spidev0.0 /dev/spidev0.1; do
    if [[ -e "$dev" ]]; then
        echo "  $dev – EXISTS"
        SPI_FOUND=true
    else
        echo "  $dev – NOT FOUND"
    fi
done

if ! $SPI_FOUND; then
    echo ""
    echo "[WARNING] No SPI devices found!"
    echo "Enable SPI on Raspberry Pi OS:"
    echo "  sudo raspi-config"
    echo "  -> Interface Options -> SPI -> Enable -> Finish -> Reboot"
    ((WARNINGS++))
fi

# Check waveshare_epd
echo ""
echo -n "waveshare_epd: "
if python3 -c "from waveshare_epd import epd2in13; print('INSTALLED')" 2>/dev/null; then
    : # printed above
else
    echo "NOT INSTALLED"
    echo "  To install for e-paper display:"
    echo "    cd ~"
    echo "    git clone https://github.com/waveshareteam/e-Paper.git"
    echo "    cd e-Paper/RaspberryPi_JetsonNano/python"
    echo "    sudo python3 setup.py install"
    ((WARNINGS++))
fi

# Summary
echo ""
if [[ $ERRORS -eq 0 && $WARNINGS -eq 0 ]]; then
    echo "=== All checks passed! ==="
    exit 0
elif [[ $ERRORS -eq 0 ]]; then
    echo "=== $WARNINGS warning(s), no errors ==="
    echo "System should work in mock mode. Install waveshare_epd for hardware."
    exit 0
else
    echo "=== $ERRORS error(s), $WARNINGS warning(s) ==="
    echo "Please fix errors before running."
    exit 1
fi
