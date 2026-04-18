#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== AI Health Board – Installer ==="

IS_PI=false
if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null || grep -q "raspberrypi" /etc/hostname 2>/dev/null; then
    IS_PI=true
fi

# Create virtual environment
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    if $IS_PI; then
        # On Pi: need --system-site-packages to access lgpio, spidev, RPi.GPIO
        # installed via apt (python3-lgpio python3-spidev python3-rpi.gpio)
        python3 -m venv --system-site-packages venv
    else
        python3 -m venv venv
    fi
else
    echo "Virtual environment already exists."
    # Warn if on Pi but venv was created without --system-site-packages
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

    # PiSugar button configuration
    echo ""
    echo "=== PiSugar Button Configuration ==="
    if command -v nc &>/dev/null; then
        if [[ -e /tmp/pisugar-server.sock ]] || pgrep -x pisugar-server &>/dev/null; then
            echo "Configuring PiSugar button events..."
            # Enable single and double tap
            echo "set_button_enable single 1" | nc -q 0 127.0.0.1 8423 2>/dev/null && echo "  Single tap: ENABLED" || echo "  Single tap: FAILED (pisugar-server not responding?)"
            echo "set_button_enable double 1" | nc -q 0 127.0.0.1 8423 2>/dev/null && echo "  Double tap: ENABLED" || echo "  Double tap: FAILED"
            echo "set_anti_mistouch 1" | nc -q 0 127.0.0.1 8423 2>/dev/null && echo "  Anti-mistouch: ENABLED" || echo "  Anti-mistouch: FAILED"
            # Set button shell commands
            echo "set_button_shell single 'kill -USR1 \$(cat /tmp/lotus-companion.pid)'" | nc -q 0 127.0.0.1 8423 2>/dev/null && echo "  Single tap -> next screen (SIGUSR1)" || echo "  Single tap shell: FAILED"
            echo "set_button_shell double 'kill -USR2 \$(cat /tmp/lotus-companion.pid)'" | nc -q 0 127.0.0.1 8423 2>/dev/null && echo "  Double tap -> tamagotchi (SIGUSR2)" || echo "  Double tap shell: FAILED"
            # Verify
            echo ""
            echo "Current button config:"
            echo "get button_shell single" | nc -q 0 127.0.0.1 8423 2>/dev/null
            echo "get button_shell double" | nc -q 0 127.0.0.1 8423 2>/dev/null
        else
            echo "pisugar-server not running. Button not configured."
            echo "Install PiSugar power manager:"
            echo "  wget -O pisugar-power-manager.sh https://cdn.pisugar.com/release/pisugar-power-manager.sh"
            echo "  bash pisugar-power-manager.sh -c release"
            echo ""
            echo "Then re-run this installer to configure button events."
        fi
    else
        echo "nc (netcat) not found. Install with: sudo apt install -y netcat-openbsd"
    fi
fi

# Copy example config if missing
if [[ ! -f "config/providers.yaml" ]]; then
    echo ""
    echo "Copying example config..."
    cp config/providers.yaml.example config/providers.yaml
    echo "  -> Edit config/providers.yaml before running"
    if $IS_PI; then
        echo "  -> Change display.backend from 'mock' to 'waveshare_2in13_v3'"
    fi
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
    echo "  1. Edit config/providers.yaml: set display.backend to 'waveshare_2in13_v3'"
    echo "  2. export GPIOZERO_PIN_FACTORY=lgpio"
    echo "  3. python app.py once"
    echo ""
    echo "Install systemd service:"
    echo "  sudo cp systemd/ai-health-board.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable ai-health-board"
    echo "  sudo systemctl start ai-health-board"
    echo ""
    echo "View logs:"
    echo "  sudo journalctl -u ai-health-board -f"
fi
