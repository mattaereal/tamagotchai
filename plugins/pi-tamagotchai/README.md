# pi-tamagotchai

pi extension that writes live session status to JSON files for the
tamagotchai-agentd daemon (file backend). No sockets; files only.

State dir: `~/.pi/agent/tamagotchai/sessions/<session-id>.json`

Install (global): `ln -s /home/senpai/tamagotchai/plugins/pi-tamagotchai ~/.pi/agent/extensions/pi-tamagotchai`

Reload in pi: `/reload`