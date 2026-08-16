#!/usr/bin/env bash
# Install the tamagotchai-agentd systemd unit (template, one per user).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SVC="/etc/systemd/system/tamagotchai-agentd@.service"

if [ ! -f "$HERE/agentd.service" ]; then
  echo "error: $HERE/agentd.service not found" >&2
  exit 1
fi

sudo cp "$HERE/agentd.service" "$SVC"
sudo systemctl daemon-reload

echo "Installed $SVC"
echo "Enable for a user:  sudo systemctl enable --now tamagotchai-agentd@<user>"
echo "Logs:               journalctl -u tamagotchai-agentd@<user> -f"
