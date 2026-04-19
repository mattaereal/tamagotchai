#!/usr/bin/env bash
set -euo pipefail

# install_services.sh - Generate and install systemd services with correct paths
# Run from inside the lotus-companion repo directory.
# Usage: sudo ./scripts/install_services.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect the actual user (even under sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [[ -z "$ACTUAL_USER" || "$ACTUAL_USER" == "root" ]]; then
    ACTUAL_USER="$(logname 2>/dev/null || whoami)"
fi
ACTUAL_HOME="$(eval echo ~${ACTUAL_USER})"

echo "=== Lotus Companion Service Installer ==="
echo "Repo:   ${REPO_DIR}"
echo "User:   ${ACTUAL_USER}"
echo "Home:   ${ACTUAL_HOME}"
echo ""

# Validate repo directory
if [[ ! -f "${REPO_DIR}/app.py" ]]; then
    echo "[ERROR] Cannot find app.py in ${REPO_DIR}"
    echo "  Run this script from inside the lotus-companion repo."
    exit 1
fi

# Validate venv for main app
if [[ ! -f "${REPO_DIR}/venv/bin/python" ]]; then
    echo "[WARNING] venv not found at ${REPO_DIR}/venv/"
    echo "  Run ./scripts/install.sh first to create the venv."
    echo "  The ai-health-board service will fail until the venv exists."
    echo ""
fi

# Check system packages for button daemon
echo "Checking system packages..."
MISSING=""
for pkg in python3-gpiozero python3-lgpio; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING="$MISSING $pkg"
    fi
done
if [[ -n "$MISSING" ]]; then
    echo "[WARNING] Missing system packages:$MISSING"
    echo "  sudo apt update && sudo apt install -y$MISSING"
    echo "  The pisugar-button service may fail without them."
    echo ""
else
    echo "System packages: OK"
fi

# Detect config path
CONFIG_PATH="${REPO_DIR}/config/providers.yaml"
if [[ ! -f "$CONFIG_PATH" ]]; then
    if [[ -f "${REPO_DIR}/config/providers.yaml.example" ]]; then
        echo "[WARNING] config/providers.yaml not found."
        echo "  Copying from example..."
        cp "${REPO_DIR}/config/providers.yaml.example" "$CONFIG_PATH"
        echo "  -> Edit ${CONFIG_PATH} before running."
    else
        echo "[ERROR] No config file found."
        exit 1
    fi
fi

echo ""
echo "--- Generating ai-health-board.service ---"

cat > /tmp/ai-health-board.service <<EOF
[Unit]
Description=AI Health Status Board
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
WorkingDirectory=${REPO_DIR}
Environment="PATH=${REPO_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="GPIOZERO_PIN_FACTORY=lgpio"
ExecStart=${REPO_DIR}/venv/bin/python ${REPO_DIR}/app.py run --config ${CONFIG_PATH}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "--- Generating pisugar-button.service ---"

cat > /tmp/pisugar-button.service <<EOF
[Unit]
Description=PiSugar S Button Daemon (GPIO3)
After=multi-user.target

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
ExecStart=/usr/bin/python3 ${REPO_DIR}/scripts/pisugar_button.py
Environment=GPIOZERO_PIN_FACTORY=lgpio
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "--- Installing services ---"

install -m 644 /tmp/ai-health-board.service /etc/systemd/system/ai-health-board.service
install -m 644 /tmp/pisugar-button.service /etc/systemd/system/pisugar-button.service
rm -f /tmp/ai-health-board.service /tmp/pisugar-button.service

systemctl daemon-reload

echo ""
echo "--- Enabling services ---"

systemctl enable ai-health-board pisugar-button

echo ""
echo "--- Starting services ---"

# Restart if already running, start if not
systemctl restart ai-health-board 2>/dev/null || systemctl start ai-health-board
systemctl restart pisugar-button 2>/dev/null || systemctl start pisugar-button

echo ""
echo "=== Done ==="
echo ""
echo "Installed services:"
echo "  ai-health-board  -> ${REPO_DIR}/app.py run"
echo "  pisugar-button   -> ${REPO_DIR}/scripts/pisugar_button.py"
echo ""
echo "Status:"
systemctl --no-pager status ai-health-board pisugar-button 2>/dev/null || true
echo ""
echo "View logs:"
echo "  sudo journalctl -u ai-health-board -f"
echo "  sudo journalctl -u pisugar-button -f"
echo ""
echo "Stop / restart:"
echo "  sudo systemctl restart ai-health-board"
echo "  sudo systemctl restart pisugar-button"
echo "  sudo systemctl stop ai-health-board pisugar-button"
echo ""
echo "Re-run this script anytime after git pull to update service paths."
