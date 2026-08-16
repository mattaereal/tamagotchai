#!/usr/bin/env bash
# Install the pi-tamagotchai extension: symlink into ~/.pi/agent/extensions
# and create the sessions dir the daemon polls.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.pi/agent/extensions/pi-tamagotchai"
SESSIONS="$HOME/.pi/agent/tamagotchai/sessions"

mkdir -p "$HOME/.pi/agent/extensions"
ln -sfn "$HERE" "$DEST"
mkdir -p "$SESSIONS"

echo "Symlinked $HERE -> $DEST"
echo "Sessions dir:  $SESSIONS"
echo "Run /reload in pi to activate."
