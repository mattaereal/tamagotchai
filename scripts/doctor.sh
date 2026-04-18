#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Health Board – Doctor ==="
echo ""

# Python version
echo -n "Python: "
python3 --version

# Config check
if [[ -f "config/providers.yaml" ]]; then
    echo "Config: found config/providers.yaml"
else
    echo "Config: missing config/providers.yaml (copy from example)"
fi

# Imports check
echo -n "Imports: "
if python3 -c "import ai_health_board" 2>/dev/null; then
    echo "OK"
else
    echo "FAIL"
fi

# SPI devices
echo ""
echo "SPI devices:"
for dev in /dev/spidev0.0 /dev/spidev0.1; do
    if [[ -e "$dev" ]]; then
        echo "  $dev – exists"
    else
        echo "  $dev – not found"
    fi
done

echo ""
echo "Enable SPI on Raspberry Pi OS:"
echo "  sudo raspi-config"
echo "  -> Interface Options -> SPI -> Enable"
echo "  -> Finish -> Yes to reboot"
echo ""
echo "=== End Doctor ==="
