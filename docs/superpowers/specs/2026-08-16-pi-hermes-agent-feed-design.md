# pi + hermes agent feed — design

**Date:** 2026-08-16
**Status:** approved (pending user spec review)
**Scope:** pi extension + always-on status daemon + display config fix. OpenCode plugin untouched. app.py refactor and repo rename out of scope.

## Problem

The display was not working as expected. Root causes, in order of severity:

1. **No feeder for pi.** The only plugin shipped is `opencode-plugin-tamagotchai`, which listens to OpenCode events. The user runs pi, not OpenCode. The "agent detail" screen has no data source.
2. **Dead URLs in `config/screens.yml`.** The OpenCode screen points at `http://192.168.1.117:7788/status`; this device is `192.168.1.103` and nothing listens on 7788 anywhere. The AI Services status board also references `127.0.0.1:7788`. Both are dead. The screen renders a setup hint forever.
3. **In-process server model is the wrong shape.** The OpenCode plugin starts an HTTP server inside the agent process. When no agent session is active, the port is closed and the display gets connection refused. This is the structural reason the screen goes dark between sessions.
4. **Stale logic fights itself.** The plugin auto-idles sessions after 60s (`STALE_TIMEOUT_MS`); the device `stale_threshold` is 120s. The plugin declares `idle` before the device ever marks `offline`, so the offline mood-map branch is unreachable.
5. **Pull-only, LAN-only.** The display polls HTTP and only reaches LAN hosts. Remote agent hosts (hermes1, hermes2) are unreachable without a tunnel.

## Goals

- pi sessions on this Pi Zero feed the display.
- Two remote hermes agents feed the display.
- Display is GET-only outbound. No inbound port on the display, no POST received by the display. Works from any network.
- Display never shows a dead screen between agent sessions: always sees `idle`/`no sessions`, never connection-refused while an agent host is up.
- Transport-agnostic. Tunnels (tailscale / cloudflared) are an ops concern, not code.
- Display rendering code stays unchanged. Only `screens.yml` URLs change.

## Non-goals

- OpenCode plugin or OpenCode screen changes (dereferenced from default config only).
- `app.py` refactor (844-line god file).
- Repo rename (`compainon` → `tamagotchai`).
- Plugin state persistence across daemon restarts (in-memory registry; agents re-heartbeat within seconds).
- pi `waiting_input` state (no native pi event exposes it).
- Multi-tenant auth on `/status` (tunnels handle access control).
- Hermes webhook event set beyond the minimal mapping needed for status + tool + session lifecycle.

## Architecture

Three components. The display stays pull-only. One daemon per agent host is the always-on seam that keeps port 7788 answering even when the agent process is down.

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT HOSTS                                                     │
│                                                                  │
│  hermes1 box:                                                    │
│    hermes ──webhook POST──► 127.0.0.1:7788/ingest  (local only)  │
│    tamagotchai-agentd (webhook backend, always-on, systemd)      │
│    cloudflared ──► https://hermes1.<tunnel>/status/all (GET)     │
│                                                                  │
│  hermes2 box: same shape                                         │
│                                                                  │
│  pi host (this Pi Zero):                                         │
│    pi + pi-tamagotchai extension                                 │
│      writes ~/.pi/agent/tamagotchai/sessions/<id>.json           │
│    tamagotchai-agentd (file backend, always-on, systemd)         │
│    serves 127.0.0.1:7788/status/all (GET)                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
               │ cloudflared / tailscale (GET only)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  DISPLAY (Pi Zero 2 W)                                           │
│                                                                  │
│  config/screens.yml (agent_feed):                                │
│    agents:                                                       │
│      - name: pi      url: http://127.0.0.1:7788/status           │
│      - name: hermes1 url: https://hermes1.<tunnel>/status        │
│      - name: hermes2 url: https://hermes2.<tunnel>/status        │
│                                                                  │
│  scheduler polls each URL every 5s (outbound GET only)           │
│  agent_feed = one row per URL. Each URL must return a SINGLE     │
│  object (dict); agent_feed overwrites `name` from config.        │
│  Use /status (not /status/all) for display. /status/all (array)  │
│  kept for debugging/future. One row per host = one session shown │
│  (latest active); multi-session-per-host visibility deferred.    │
└──────────────────────────────────────────────────────────────────┘
```

**Why one daemon per host, not one central daemon:** the display's `agent_feed` screen already aggregates multiple URLs. Reusing it means each host self-contains its own state source. No central point of failure, no central network dependency.

**Why a daemon at all (vs. agent serving `/status` directly):** pi's extension lifecycle forbids starting sockets from the factory; sockets must start on `session_start` and close on `session_shutdown`. Between sessions the port is closed and the display gets connection refused. hermes is similarly not guaranteed always running. The daemon is the always-on wrapper whose single job is to keep 7788 answering `idle`/`no sessions` when the agent process is down.

## Components

### 2.1 — `plugins/pi-tamagotchai/` (pi extension)

**Purpose:** translate pi session events into a state file on disk. No sockets.

**Layout:**
```
plugins/pi-tamagotchai/
├── package.json          # name, pi.extensions entry, no runtime deps
├── tsconfig.json
├── README.md
└── src/
    └── index.ts          # default factory: pi.on(...) → writeState()
```

**State dir:** `~/.pi/agent/tamagotchai/sessions/<session-id>.json`

**Event → status mapping:**

| pi event | status | message | metadata updates |
|---|---|---|---|
| `session_start` (any reason) | `working` | `session started` | `project`, `session_id`, `start_time_ms` |
| `before_agent_start` | `working` | first 60 chars of `event.prompt` | — |
| `tool_execution_start` | `working` | `tool: <toolName>` | `tool_name` |
| `tool_execution_end` | `working` (success) / `error` (`isError`) | `tool: <toolName>` | `tools_executed`++ |
| `turn_start` | `working` | — | `turn_count`++ |
| `turn_end` | `working` | — | — |
| `message_end` (assistant) | `working` | — | accumulate `tokens_input/output/total`, `cost_usd` from `event.message.usage`; set `model` from `ctx.model` |
| `agent_settled` | `idle` | `settled` | `session_duration_ms` = now − `start_time_ms` |
| `session_shutdown` | — | — | **delete file** |

**Payload written to disk** (Standard Agent Status JSON):
```json
{
  "session_id": "<pi session id>",
  "status": "working",
  "message": "tool: bash",
  "last_heartbeat": "2026-08-16T10:35:22Z",
  "pending": 1,
  "metadata": {
    "project": "tamagotchai",
    "model": "anthropic/claude-3.7-sonnet",
    "tool_name": "bash",
    "turn_count": 5,
    "tools_executed": 12,
    "tokens_input": 1240,
    "tokens_output": 340,
    "tokens_total": 1580,
    "cost_usd": 0.0042,
    "session_duration_ms": 245000,
    "source": "pi"
  }
}
```

**Write semantics:** atomic — write to `<id>.json.tmp`, then `os.replace` to `<id>.json`. Cheap at event rates. Idempotent across reloads (`session_start` reason `reload` rewrites the file).

**`waiting_input`:** skipped for pi. No native pi event exposes a permission-prompt state. Reserved for hermes.

**Install:** `ln -s /home/senpai/tamagotchai/plugins/pi-tamagotchai /home/senpai/.pi/agent/extensions/pi-tamagotchai`. Hot-reloadable via `/reload`.

### 2.2 — `plugins/tamagotchai-agentd/` (always-on daemon)

**Purpose:** watch state sources on one host, serve aggregated Standard Agent Status JSON over HTTP. One daemon per agent host.

**Language:** Python. Matches the repo, stdlib `http.server` suffices. Optional `watchdog` dep; polling at 1s is fine for display poll rates.

**Layout:**
```
plugins/tamagotchai-agentd/
├── agentd.py             # entrypoint
├── backends/
│   ├── __init__.py
│   ├── file_watch.py     # pi: poll ~/.pi/agent/tamagotchai/sessions/
│   └── webhook.py        # hermes: /ingest receiver, HMAC verify
├── state.py              # in-memory session registry, stale sweep
├── server.py             # /status, /status/all, /health
├── config.py             # CLI args + env
├── agentd.service        # systemd template
├── requirements.txt      # watchdog (optional)
└── README.md
```

**Backends (selected via `--backend`):**

- **`file` (pi hosts):** polls `~/.pi/agent/tamagotchai/sessions/*.json` every 1s. Each file = one session. Missing/deleted file = session gone. Stale file (heartbeat older than `--stale-secs`, default 120) → status overwritten to `offline` in served payload.
- **`webhook` (hermes hosts):** HTTP POST `/ingest`. Body = hermes webhook payload. HMAC-SHA256 verified against `--secret` / `HERMES_WEBHOOK_SECRET`. Translates hermes hook events → Standard Agent Status JSON, stores in the same in-memory registry. Entries expire after `--stale-secs` of no new webhook.

**Hermes webhook → status mapping** (minimal, refine at implementation against the actual registered event list in `agent/outbound_webhooks.py`):

| hermes hook event | status | notes |
|---|---|---|
| `on_session_start` (or first event for `session_id`) | `working` | register session |
| `pre_tool_call` | `working` | `message` = `tool: <tool_name>`, `metadata.tool_name` |
| `post_tool_call` | `success` (no error) / `error` | `tools_executed`++ |
| `on_message` (if emitted) | `working` | accumulate tokens/cost/model if in payload |
| `on_session_end` | `idle` then expire | mark idle, drop after grace |
| `subagent_stop` | `working` (parent still active) | `metadata.subagents_done`++ |

Hermes webhook payloads include `session_id`, `tool_name`, `tool_input`, `extra` — enough to fill the Standard schema.

**Endpoints (all GET, all JSON, except `/ingest`):**

| Path | Method | Returns |
|---|---|---|
| `/health` | GET | `200 ok` (liveness; used by cloudflared health checks) |
| `/status` | GET | latest active session payload, or `{status:"idle", message:"no sessions", last_heartbeat:<now>, pending:0, metadata:{}}` if none |
| `/status/all` | GET | array of all live session payloads, sorted by `last_heartbeat` desc |
| `/ingest` | POST | webhook receiver (webhook backend only); `204` on accept, `401` on bad signature |

**Bind:** `0.0.0.0:7788` by default; `--host` / `--port` override. Behind cloudflared or tailscale.

**Stale sweep:** background thread every `--stale-secs / 2`. Sessions older than `--stale-secs` → `status` overwritten to `offline` in served payload. Sessions with no heartbeat for `2 * --stale-secs` → dropped from registry. **The daemon owns staleness.** Agents only heartbeat; they never self-idle. This fixes the opencode-plugin 60s/120s mismatch.

**systemd unit:** `tamagotchai-agentd.service`, `Restart=always`, `User=<agent user>`, `Environment=TAMAGOTCHAI_PORT=7788`, `Environment=TAMAGOTCHAI_BACKEND=file|webhook`. Documented in the daemon README.

### 2.3 — Display config (`config/screens.yml`)

Replace the dead-URL `opencode` screen with an `agent_feed` pulling from real hosts. Keep `AI Services` and `Device` screens. Drop the dead `OpenCode` category from the AI Services board.

```yaml
screens:
  - name: Agents
    type: agent_feed
    poll_interval: 5
    display_duration: 15
    stale_threshold: 120
    agents:
      - name: pi
        url: http://127.0.0.1:7788/status/all
      - name: hermes1
        url: https://hermes1.<your-cf-tunnel>.com/status
      - name: hermes2
        url: https://hermes2.<your-cf-tunnel>.com/status

  - name: AI Services
    type: status_board
    poll_interval: 60
    display_duration: 15
    categories:
      - name: OpenAI
        url: https://status.openai.com/api/v2/summary.json
        type: statuspage
        icon: openai
        items:
          - key: Overall
            label: API
      - name: Anthropic
        url: https://status.claude.com/api/v2/summary.json
        type: statuspage
        icon: anthropic
        items:
          - key: Overall
            label: AI
      - name: GitHub
        url: https://www.githubstatus.com/api/v2/summary.json
        type: statuspage
        icon: github
        items:
          - key: Overall
            label: GH

  - name: Device
    type: device_status
    poll_interval: 30
    display_duration: 15
```

**pi location confirmed:** pi runs on this Pi Zero. `127.0.0.1:7788` is correct and the daemon runs here too. pi is also a displayed agent alongside hermes1 and hermes2.

## Data flow

### pi path (this box)
1. pi session event → extension handler builds payload dict.
2. Handler atomically writes `~/.pi/agent/tamagotchai/sessions/<session-id>.json`.
3. Daemon file backend polls the dir at 1s, reads the file, updates the in-memory registry.
4. Display polls `http://127.0.0.1:7788/status` every 5s → receives single object including the pi session.
5. `agent_feed` layout renders one row per configured URL.

### hermes path (hermes1, hermes2)
1. hermes emits a hook event → outbound webhook POSTs to `http://127.0.0.1:7788/ingest` (localhost on the hermes box).
2. Daemon webhook backend verifies HMAC-SHA256, translates payload, updates the registry.
3. cloudflared exposes `https://hermesN.<tunnel>/status/all` publicly.
4. Display polls that URL every 5s → single object including the hermes session.
5. Same `agent_feed` row (one row per configured URL).

### No-agent path (display still works)
- Daemon up, no sessions registered → `/status` returns the idle payload `{status:"idle", message:"no sessions", ...}`; `/status/all` returns `[]`.
- `agent_feed` renders one row per configured URL. An idle host shows `[+] <name> idle`. Verified: `agent_feed.py` handles a non-dict JSON by wrapping it, and the layout maps `status:"idle"` → `[+]` (`ui/layouts/agent_feed.py:14`). No crash on idle payloads.
- All-fetches-failed (every URL connection-refused) → `show_hint=True` → layout renders the "No agent data." hint block (`ui/layouts/agent_feed.py:120-132`). Already handled; no new code needed.
- Empty `agents:` config list → `fetch()` returns early (`agent_feed.py:46-47`), renders `num_agents=0` with no rows. Doesn't crash.

## Error and stale handling

**Daemon always answers 200 while up.** The only failure modes:

- **Agent host down / tunnel down** → display fetch times out at 10s (existing `aiohttp` timeout) → that agent's row shows `[-] connection error` (existing `agent_feed` behavior).
- **Daemon up, no sessions** → idle row, not error.
- **Stale session** (heartbeat older than `stale_threshold`, default 120s) → daemon overwrites `status` to `offline` in the served payload. Display's `agent_feed` already maps `offline` → `[-]` icon. Single source of truth: the daemon owns staleness; agents only heartbeat.
- **Dead session** (no heartbeat for `2 * stale_threshold`) → daemon drops from registry. File backend: file deleted. Webhook backend: entry expired.
- **HMAC failure on `/ingest`** → `401` + log. No state change. Display unaffected.
- **Malformed state file** (file backend) → log warning, skip file, do not crash. Next write fixes it.
- **Daemon crash** → systemd `Restart=always`. In-memory registry rebuilds from files (file backend) or from the next webhook (webhook backend; acceptable — hermes re-emits within seconds).

Display side is unchanged: `agent_feed` already has `__fetch_error` → `[-] connection error`, stale detection, and status icons. We only feed it good URLs.

## Testing

### pi extension (TypeScript)
- Unit: event → payload mapping (table-driven tests for each pi event).
- Unit: atomic write produces valid JSON at the expected path.
- Unit: `session_shutdown` deletes the file.
- Integration (best effort): spawn pi with `-e ./src/index.ts`, fire a mock `tool_call` event, assert file appears. If hard to drive programmatically, fall back to unit tests on pure handler functions extracted from the factory.

### daemon (Python)
- Unit: file backend reads a temp sessions dir, serves `/status/all` correctly.
- Unit: webhook backend verifies HMAC (good sig 204, bad sig 401, missing sig 401).
- Unit: stale sweep marks `offline` after threshold, drops after 2x.
- Unit: `/health` returns 200.
- Unit: empty registry → `/status` returns idle payload, `/status/all` returns `[]`.
- Integration: start daemon on a random port, curl endpoints, assert shapes match Standard Agent Status JSON.
- Integration: write a session file, poll `/status/all`, assert it appears; delete file, assert it disappears.

### display config
- `python app.py preview` renders the `Agents` screen from a mocked `agent_feed` payload.
- `python app.py once` on this Pi's actual e-paper for a visual check.
- Existing `test_new_modules.py` / `test_ui_layout.py` cover `agent_feed` rendering; new config needs a smoke test that it loads.

### Live test on this Pi (hardware)
1. Build the pi extension, symlink, `/reload` pi.
2. Start the daemon locally: `python plugins/tamagotchai-agentd/agentd.py --backend file`.
3. Run `python app.py once` → see the pi row on e-paper.
4. Trigger a pi action (this very session) → watch the row update to `working`.
5. Stop pi → row goes `idle` then `offline` after 120s.

### Test file locations
- `tests/test_pi_extension.py` or `plugins/pi-tamagotchai/test/` (decided at plan time).
- `tests/test_agentd.py`.

## Open questions for implementation
- Exact hermes webhook event names (verify against `agent/outbound_webhooks.py`'s registered event list at implementation time).
- Whether to also surface a `waiting_input` state for hermes (its `permission.asked` equivalent) — defer until hermes webhook event set is confirmed.
- Multi-session-per-host visibility: current design shows one row per host (latest active session via `/status`). If multiple concurrent sessions per host must all be visible, that requires a display-side change to `agent_feed` (flatten array responses) — explicitly deferred.

## Out of scope (restated)
- OpenCode plugin + OpenCode screen (untouched; dereferenced from default config).
- `app.py` refactor.
- Repo rename.
- Plugin state persistence across daemon restarts.
- pi `waiting_input` state.
- Multi-tenant auth on `/status`.