#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "=== AI Health Board – Installer ==="

# Detect user
if [[ "$USER" == "root" ]]; then
    echo "[WARNING] Running as root. This is not recommended."
    echo "  The systemd service expects to run as 'pi' user."
    echo "  Consider running as a regular user instead."
fi

# Create virtual environment if not present
if [[ ! -d "venv" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Copy example config if missing
if [[ ! -f "config/providers.yaml" ]]; then
    echo "Copying example config..."
    cp config/providers.yaml.example config/providers.yaml
    echo "  → Edit config/providers.yaml before running"
else
    echo "Config already exists, skipping copy."
fi

# Run doctor to check environment
echo ""
echo "Running doctor check..."
python app.py doctor || true

echo ""
echo "=== Installation complete ==="
echo ""
echo "To test (mock mode, no hardware required):"
echo "  source venv/bin/activate"
echo "  python app.py preview"
echo ""
echo "To run once with actual display:"
echo "  1. Edit config/providers.yaml and set display.backend to 'waveshare_2in13'"
echo "  2. python app.py once"
echo ""
echo "To install as a systemd service:"
echo "  1. Edit systemd/ai-health-board.service and update paths if needed"
echo "  2. sudo cp systemd/ai-health-board.service /etc/systemd/system/"
echo "  3. sudo systemctl daemon-reload"
echo "  4. sudo systemctl enable ai-health-board"
echo "  5. sudo systemctl start ai-health-board"
echo ""
echo "View logs:"
echo "  sudo journalctl -u ai-health-board -f"
