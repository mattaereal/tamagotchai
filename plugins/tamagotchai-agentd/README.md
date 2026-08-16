# tamagotchai-agentd

Always-on HTTP daemon serving [Standard Agent Status JSON](../../AGENTS.md#standard-agent-status-json)
on `0.0.0.0:7788`. Keeps port 7788 answering `idle`/`no sessions` even when no
agent session is active, so the e-paper display never sees a connection error
while the daemon itself is up.

One daemon runs **per agent host**:

- On a **pi** host, it runs with the `file` backend and polls session JSON files
  written by the [`pi-tamagotchai`](../pi-tamagotchai/) extension.
- On a **hermes** host, it runs with the `webhook` backend and receives
  HMAC-signed POSTs at `/ingest` from hermes outbound webhooks.

The display's `agent_feed` screen polls each daemon's `/status/all` endpoint
(GET only) and aggregates the rows.

## Architecture

```
 pi process                  hermes process
 ┌─────────────────┐         ┌─────────────────┐
 │ pi-tamagotchai  │         │ hermes          │
 │ extension       │         │ (outbound hook) │
 │ writes files    │         │  POSTs /ingest  │
 └──────┬──────────┘         └──────┬──────────┘
        │ files                     │ HTTPS + HMAC
        ▼                           ▼
 ┌─────────────────┐         ┌─────────────────┐
 │ tamagotchai-    │         │ tamagotchai-    │
 │ agentd (file)   │         │ agentd (webhook)│
 │ 0.0.0.0:7788    │         │ 0.0.0.0:7788    │
 └──────┬──────────┘         └──────┬──────────┘
        │ GET /status/all           │ GET /status/all
        └────────────┬──────────────┘
                     ▼
        ┌─────────────────────────┐
        │ tamagotchi display      │
        │ agent_feed screen       │
        └─────────────────────────┘
```

The daemon owns staleness. Agents only heartbeat; they never self-idle.
Stale (`> stale_threshold`) → `offline`; dead (`> 2 * stale_threshold`) → dropped.

## Backends

- `file` (pi hosts): polls `~/.pi/agent/tamagotchai/sessions/*.json` written by
  the pi-tamagotchai extension. Atomic writes (temp + `os.replace`) on the
  writer side; the daemon re-reads each poll.
- `webhook` (hermes hosts): receives HMAC-SHA256 signed POSTs at `/ingest` from
  hermes outbound webhooks. Verifies `X-Tamagotchai-Signature: sha256=<hex>`
  against `HERMES_WEBHOOK_SECRET`. Maps hermes events to the Standard Agent
  Status JSON fields.

## Endpoints

- `GET /health` → `ok` (plain text)
- `GET /status` → latest active session (dict). Returns an idle payload when no
  sessions are live — never connection-refuses while the daemon is up.
- `GET /status/all` → all live sessions (array). Empty array when none.
- `POST /ingest` → webhook receiver (webhook backend only).
  - `204` accept, `401` bad signature, `400` bad JSON.

## Run

    PYTHONPATH=plugins python plugins/tamagotchai-agentd/agentd.py --backend file --port 7788

Env overrides: `TAMAGOTCHAI_BACKEND`, `TAMAGOTCHAI_HOST`, `TAMAGOTCHAI_PORT`,
`TAMAGOTCHAI_SESSIONS_DIR`, `TAMAGOTCHAI_STALE_SECS`, `TAMAGOTCHAI_POLL_INTERVAL`,
`HERMES_WEBHOOK_SECRET`.

## Install (systemd)

    ./plugins/tamagotchai-agentd/install.sh
    sudo systemctl enable --now tamagotchai-agentd@<user>

Logs: `journalctl -u tamagotchai-agentd@<user> -f`

The unit template (`agentd.service`) is parameterised by user so each account
runs its own daemon. `%i` expands to the username passed to `systemctl enable`.

## Transport

Bind is `0.0.0.0:7788`. Reach it via tailscale or cloudflared. The daemon is
transport-agnostic — no tunnel code here. Expose `https://<host>.<tunnel>/`
and point the display's `screens.yml` at it.

## Webhook backend: hermes event map

Hermes outbound webhook events are mapped to Standard Agent Status JSON:

| Hermes event | Agent `status` | Notes |
|---|---|---|
| `session.start` | `working` | project from payload |
| `agent.start` | `working` | message from prompt (truncated) |
| `tool.start` | `working` | `metadata.tool_name` set |
| `tool.end` | `error` on failure, else `working` | increments `tools_executed` |
| `message.end` | (unchanged) | accumulates tokens + cost |
| `agent.settled` | `idle` | `pending = 0` |
| `session.shutdown` | file removed | session dropped from registry |

## Live integration test (Pi Zero)

1. `./plugins/pi-tamagotchai/install.sh` then `/reload` in pi.
2. `./plugins/tamagotchai-agentd/install.sh && sudo systemctl enable --now tamagotchai-agentd@senpai`
3. `curl http://127.0.0.1:7788/status/all` → array with one pi session (`working`).
4. `python app.py once` → e-paper shows the pi row in `Agents`.
5. Trigger a pi action in this very session → `curl .../status/all` shows
   `working` + `tool: ...`.
6. Stop pi (`/quit`) → row stays for `stale_threshold` then goes `offline`
   after 120s.
7. Hermes: on each hermes host, install the daemon with
   `TAMAGOTCHAI_BACKEND=webhook`, set `HERMES_WEBHOOK_SECRET`, point hermes
   `hooks.outbound` at `http://127.0.0.1:7788/ingest`, expose
   `https://hermesN.<tunnel>/status/all` via cloudflared.
8. Fill real tunnel hostnames into `config/screens.yml`, `python app.py once`
   → all three rows live.

## Tests

    python -m pytest tests/test_agentd_state.py tests/test_agentd_server.py \
      tests/test_agentd_file_watch.py tests/test_agentd_webhook.py \
      tests/test_agentd_config.py -v
