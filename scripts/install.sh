#!/usr/bin/env bash
set -euo pipefail

echo "=== AI Health Board – Installer ==="

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

# Install systemd service
echo ""
echo "To install as a systemd service (recommended):"
echo "  sudo cp systemd/ai-health-board.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable ai-health-board"
echo "  sudo systemctl start ai-health-board"
echo ""
echo "Or run manually:"
echo "  source venv/bin/activate"
echo "  python app.py once --config config/providers.yaml"
echo ""
echo "=== Installation complete ==="
