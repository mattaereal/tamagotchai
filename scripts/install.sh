#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== Tamagotchai Installer ==="

IS_PI=false
if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null || grep -q "raspberrypi" /etc/hostname 2>/dev/null; then
    IS_PI=true
fi

# Create virtual environment
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    if $IS_PI; then
        python3 -m venv --system-site-packages venv
    else
        python3 -m venv venv
    fi
else
    echo "Virtual environment already exists."
    if $IS_PI; then
        if ! grep -q "system-site-packages = true" venv/pyvenv.cfg 2>/dev/null; then
            echo "[WARNING] venv was created without --system-site-packages."
            echo "  Pi system packages (lgpio, spidev) won't be accessible."
            echo "  To fix: rm -rf venv && ./scripts/install.sh"
        fi
    fi
fi

source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Pi-specific setup
if $IS_PI; then
    echo ""
    echo "=== Raspberry Pi detected ==="

    # Check system packages
    echo "Checking system packages..."
    MISSING_APT=""
    for pkg in python3-lgpio python3-spidev python3-rpi.gpio; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            MISSING_APT="$MISSING_APT $pkg"
        fi
    done
    if [[ -n "$MISSING_APT" ]]; then
        echo "Missing system packages:$MISSING_APT"
        echo "  sudo apt update && sudo apt install -y$MISSING_APT"
    else
        echo "System packages: OK"
    fi

    # Check waveshare_epd
    if python3 -c "from waveshare_epd import epd2in13_V3" 2>/dev/null; then
        echo "waveshare_epd (V3): INSTALLED"
    else
        echo "waveshare_epd (V3): NOT INSTALLED"
        echo "  To install:"
        echo "    cd ~"
        echo "    git clone https://github.com/waveshareteam/e-Paper.git"
        echo "    cd e-Paper/RaspberryPi_JetsonNano/python"
        echo "    sudo apt install -y python3-setuptools"
        echo "    sudo python3 setup.py install"
    fi

    # Check SPI
    if [[ -e /dev/spidev0.0 ]]; then
        echo "SPI: ENABLED"
    else
        echo "SPI: NOT ENABLED"
        echo "  sudo raspi-config -> Interface Options -> SPI -> Enable -> Reboot"
    fi

    # Check GPIOZERO_PIN_FACTORY
    echo ""
    echo "Important: Set GPIO pin factory for Trixie/Bookworm:"
    echo "  export GPIOZERO_PIN_FACTORY=lgpio"
    echo "  (Add to ~/.bashrc or set in systemd service)"

    # PiSugar button daemon
    echo ""
    echo "=== PiSugar Button Daemon ==="
    if python3 -c "from gpiozero import Button" 2>/dev/null; then
        echo "gpiozero: OK"
    else
        echo "gpiozero: MISSING"
        echo "  sudo apt install -y python3-gpiozero"
    fi

    echo ""
    echo "PiSugar S button is connected to GPIO3 (pin 5)."
    echo "The button daemon reads GPIO3 directly (no I2C needed)."
    echo ""
    echo "Disable I2C if pisugar-server is interfering:"
    echo "  sudo raspi-config -> Interface Options -> I2C -> Disable"
    echo "  sudo systemctl stop pisugar-server 2>/dev/null"
    echo "  sudo systemctl disable pisugar-server 2>/dev/null"
fi

# Run init wizard if no config exists
if [[ ! -f "config/display.yml" ]] || [[ ! -f "config/screens.yml" ]]; then
    echo ""
    echo "Config files not found. Running setup wizard..."
    python app.py init
else
    echo "Config already exists."
fi

echo ""
echo "=== Installation complete ==="
echo ""
echo "Quick test (mock mode, any machine):"
echo "  source venv/bin/activate"
echo "  python app.py preview"
echo ""
if $IS_PI; then
    echo "On Pi with e-paper display:"
    echo "  1. Edit config/display.yml: set backend to your display version"
    echo "  2. export GPIOZERO_PIN_FACTORY=lgpio"
    echo "  3. python app.py once"
    echo ""
    echo "Install systemd services:"
    echo "  sudo ./scripts/install_services.sh"
    echo ""
    echo "View logs:"
    echo "  sudo journalctl -u tamagotchai -f"
    echo "  sudo journalctl -u pisugar-button -f"
fi
