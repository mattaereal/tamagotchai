#!/usr/bin/env bash
set -euo pipefail

# install_services.sh - Generate and install systemd services with correct paths
# Run from inside the tamagotchai repo directory.
# Usage: sudo ./scripts/install_services.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Detect the actual user (even under sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
if [[ -z "$ACTUAL_USER" || "$ACTUAL_USER" == "root" ]]; then
    ACTUAL_USER="$(logname 2>/dev/null || whoami)"
fi
ACTUAL_HOME="$(eval echo ~${ACTUAL_USER})"

echo "=== Tamagotchai Service Installer ==="
echo "Repo:   ${REPO_DIR}"
echo "User:   ${ACTUAL_USER}"
echo "Home:   ${ACTUAL_HOME}"
echo ""

# Validate repo directory
if [[ ! -f "${REPO_DIR}/app.py" ]]; then
    echo "[ERROR] Cannot find app.py in ${REPO_DIR}"
    echo "  Run this script from inside the tamagotchai repo."
    exit 1
fi

# Validate venv for main app
if [[ ! -f "${REPO_DIR}/venv/bin/python" ]]; then
    echo "[WARNING] venv not found at ${REPO_DIR}/venv/"
    echo "  Run ./scripts/install.sh first to create the venv."
    echo "  The tamagotchai service will fail until the venv exists."
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

# Detect config directory
CONFIG_DIR="${REPO_DIR}/config"
if [[ ! -f "${CONFIG_DIR}/display.yml" ]]; then
    echo "[WARNING] config/display.yml not found."
    echo "  Run 'python app.py init' to generate config files."
fi

echo ""
echo "--- Generating tamagotchai.service ---"

cat > /tmp/tamagotchai.service <<EOF
[Unit]
Description=Tamagotchai - AI Status Companion
After=network.target

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
WorkingDirectory=${REPO_DIR}
Environment="PATH=${REPO_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="GPIOZERO_PIN_FACTORY=lgpio"
ExecStart=${REPO_DIR}/venv/bin/python ${REPO_DIR}/app.py run --config ${CONFIG_DIR}
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

# --- Wi-Fi setup services (if wifi/ exists) ---

WIFI_DIR="${REPO_DIR}/wifi"
if [[ -d "$WIFI_DIR" && -f "${WIFI_DIR}/provisioning/app.py" ]]; then
    echo "--- Generating wifi-setup.service ---"

    cat > /tmp/wifi-setup.service <<EOF
[Unit]
Description=Wi-Fi Setup Onboarding Service (automatic fallback)
After=NetworkManager.service network-online.target
Wants=NetworkManager.service
StartLimitIntervalSec=120
StartLimitBurst=3

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
WorkingDirectory=${WIFI_DIR}
ExecStart=/usr/bin/python3 -m provisioning.app
ExecStop=${WIFI_DIR}/scripts/stop_setup_mode.sh
Restart=on-failure
RestartSec=15
StandardOutput=journal
StandardError=journal

Environment=WIFI_SETUP_BOOT_TIMEOUT=45
Environment=WIFI_SETUP_IDLE_TIMEOUT=600
Environment=WIFI_SETUP_HOTSPOT_SSID=TAMAGOTCHAI-SETUP
Environment=WIFI_SETUP_HOTSPOT_IP=10.42.0.1
Environment=WIFI_SETUP_WEB_PORT=80
Environment=WIFI_SETUP_DISPLAY_HOOK=ai_health_board.wifi_display_hook
Environment=PYTHONPATH=${REPO_DIR}

[Install]
WantedBy=multi-user.target
EOF

    echo "--- Generating wifi-setup-trigger.service ---"

    cat > /tmp/wifi-setup-trigger.service <<EOF
[Unit]
Description=Wi-Fi Setup Onboarding Service (trigger file)
After=NetworkManager.service
Wants=NetworkManager.service
ConditionPathExistsGlob=|/boot/setup-wifi
ConditionPathExistsGlob=|/boot/firmware/setup-wifi

[Service]
Type=simple
User=${ACTUAL_USER}
Group=${ACTUAL_USER}
WorkingDirectory=${WIFI_DIR}
ExecStart=/usr/bin/python3 -m provisioning.app
ExecStop=${WIFI_DIR}/scripts/stop_setup_mode.sh
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=WIFI_SETUP_BOOT_TIMEOUT=45
Environment=WIFI_SETUP_IDLE_TIMEOUT=600
Environment=WIFI_SETUP_HOTSPOT_SSID=TAMAGOTCHAI-SETUP
Environment=WIFI_SETUP_HOTSPOT_IP=10.42.0.1
Environment=WIFI_SETUP_WEB_PORT=80
Environment=WIFI_SETUP_DISPLAY_HOOK=ai_health_board.wifi_display_hook
Environment=PYTHONPATH=${REPO_DIR}

[Install]
WantedBy=multi-user.target
EOF

    WIFI_SERVICES="wifi-setup wifi-setup-trigger"
else
    echo "[SKIP] wifi/ directory not found, skipping wifi services"
    WIFI_SERVICES=""
fi

echo "--- Installing services ---"

install -m 644 /tmp/tamagotchai.service /etc/systemd/system/tamagotchai.service
install -m 644 /tmp/pisugar-button.service /etc/systemd/system/pisugar-button.service
rm -f /tmp/tamagotchai.service /tmp/pisugar-button.service

if [[ -n "$WIFI_SERVICES" ]]; then
    install -m 644 /tmp/wifi-setup.service /etc/systemd/system/wifi-setup.service
    install -m 644 /tmp/wifi-setup-trigger.service /etc/systemd/system/wifi-setup-trigger.service
    rm -f /tmp/wifi-setup.service /tmp/wifi-setup-trigger.service
fi

systemctl daemon-reload

echo ""
echo "--- Enabling services ---"

systemctl enable tamagotchai pisugar-button $WIFI_SERVICES

echo ""
echo "--- Starting services ---"

systemctl restart tamagotchai 2>/dev/null || systemctl start tamagotchai
systemctl restart pisugar-button 2>/dev/null || systemctl start pisugar-button
for svc in $WIFI_SERVICES; do
    systemctl restart "$svc" 2>/dev/null || systemctl start "$svc"
done

echo ""
echo "=== Done ==="
echo ""
echo "Installed services:"
echo "  tamagotchai      -> ${REPO_DIR}/app.py run"
echo "  pisugar-button   -> ${REPO_DIR}/scripts/pisugar_button.py"
if [[ -n "$WIFI_SERVICES" ]]; then
echo "  wifi-setup       -> ${WIFI_DIR}/provisioning/ (auto-fallback)"
echo "  wifi-setup-trigger -> ${WIFI_DIR}/provisioning/ (trigger file only)"
fi
echo ""
echo "Status:"
systemctl --no-pager status tamagotchai pisugar-button $WIFI_SERVICES 2>/dev/null || true
echo ""
echo "View logs:"
echo "  sudo journalctl -u tamagotchai -f"
echo "  sudo journalctl -u pisugar-button -f"
if [[ -n "$WIFI_SERVICES" ]]; then
echo "  sudo journalctl -u wifi-setup -f"
fi
echo ""
echo "Stop / restart:"
echo "  sudo systemctl restart tamagotchai"
echo "  sudo systemctl restart pisugar-button"
echo "  sudo systemctl stop tamagotchai pisugar-button"
if [[ -n "$WIFI_SERVICES" ]]; then
echo "  sudo systemctl restart wifi-setup"
fi
echo ""
echo "Re-run this script anytime after git pull to update service paths."
