#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Required on Raspberry Pi OS Trixie/Bookworm
export GPIOZERO_PIN_FACTORY=lgpio

if [[ -d "venv" ]]; then
    source venv/bin/activate
fi

exec python app.py once --config config
