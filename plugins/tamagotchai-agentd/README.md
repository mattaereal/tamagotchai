# tamagotchai-agentd

Always-on HTTP daemon serving Standard Agent Status JSON on `0.0.0.0:7788`.
Keeps port 7788 answering `idle`/`no sessions` even when the agent process is down.

## Backends

- `file` (pi hosts): polls `~/.pi/agent/tamagotchai/sessions/*.json` written by the pi-tamagotchai extension.
- `webhook` (hermes hosts): receives HMAC-signed POSTs at `/ingest` from hermes outbound webhooks.

## Endpoints

- `GET /health` -> `ok`
- `GET /status` -> latest active session (dict)
- `GET /status/all` -> all live sessions (array)
- `POST /ingest` -> webhook receiver (webhook backend only; 204 accept, 401 bad sig, 400 bad json)

## Run

    PYTHONPATH=plugins python plugins/tamagotchai-agentd/agentd.py --backend file --port 7788

Env overrides: `TAMAGOTCHAI_BACKEND`, `TAMAGOTCHAI_HOST`, `TAMAGOTCHAI_PORT`,
`TAMAGOTCHAI_SESSIONS_DIR`, `TAMAGOTCHAI_STALE_SECS`, `TAMAGOTCHAI_POLL_INTERVAL`,
`HERMES_WEBHOOK_SECRET`.

## systemd

    sudo cp agentd.service /etc/systemd/system/tamagotchai-agentd@.service
    sudo systemctl enable --now tamagotchai-agentd@<user>

## Transport

Bind is 0.0.0.0:7788. Reach it via tailscale or cloudflared. The daemon is
transport-agnostic — no tunnel code here.