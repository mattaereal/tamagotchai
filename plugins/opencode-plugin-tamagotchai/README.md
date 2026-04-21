# opencode-plugin-tamagotchai

OpenCode plugin that exposes live agent status via HTTP for [Tamagotchai](https://github.com/yourusername/tamagotchai) e-paper displays.

## What it does

Instead of exporting telemetry via OpenTelemetry, this plugin starts a lightweight HTTP server inside the OpenCode process and serves the **Standard Agent Status JSON** directly. This means:

- **Zero overhead** on your Raspberry Pi -- Tamagotchai just polls HTTP like any other screen
- **Zero OTEL complexity** -- no collectors, no protobuf, no bridges
- **Instant status updates** -- in-memory state updates on every OpenCode event
- **Rich metadata** -- model name, token counts, cost, files modified, message count, project name

## Installation

### Method 1: Auto-discovery (recommended)

Copy the plugin into OpenCode's plugin directory. OpenCode automatically loads all `.ts` and `.js` files from here at startup:

```bash
mkdir -p ~/.config/opencode/plugins
cp /path/to/tamagotchai/plugins/opencode-plugin-tamagotchai/src/index.ts ~/.config/opencode/plugins/tamagotchai.ts
```

That's it. No config editing needed.

### Method 2: Config file reference

Edit `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["/absolute/path/to/tamagotchai/plugins/opencode-plugin-tamagotchai/src/index.ts"]
}
```

**Note:** The path must be absolute. Relative paths resolve from OpenCode's CWD and often break.

## Configuration

Environment variables (optional):

| Variable | Default | Description |
|---|---|---|
| `TAMAGOTCHAI_PORT` | `7788` | HTTP port for the status server |
| `TAMAGOTCHAI_HOST` | `0.0.0.0` | Bind address (`127.0.0.1` for local-only) |

## Endpoints

Once OpenCode is running with this plugin enabled:

- `GET http://localhost:7788/status` -- Standard Agent Status JSON
- `GET http://localhost:7788/health` -- Plain text `ok`

### Example response

```json
{
  "status": "working",
  "message": "cmd: bash",
  "last_heartbeat": "2026-04-20T10:35:22.000Z",
  "pending": 1,
  "metadata": {
    "project": "tamagotchai",
    "model": "anthropic/claude-3.7-sonnet",
    "tokens_input": 1240,
    "tokens_output": 340,
    "tokens_total": 1580,
    "cost_usd": 0.0042,
    "session_duration_ms": 245000,
    "tool_name": "bash",
    "message_count": 5,
    "files_modified": 3,
    "commits": 2,
    "lines_added": 45,
    "lines_removed": 12
  }
}
```

**Note:** Null/empty fields are omitted from the JSON. Only populated fields appear.

## Tracked Metadata

| Field | Source | Description |
|---|---|---|
| `project` | Plugin context | Project name from directory or OpenCode project |
| `model` | `message.updated` | Active LLM model (e.g. `anthropic/claude-3.7-sonnet`) |
| `tokens_input` | `message.part.updated` (step-finish) | Cumulative input tokens this session |
| `tokens_output` | `message.part.updated` (step-finish) | Cumulative output tokens this session |
| `tokens_total` | `message.part.updated` (step-finish) | Cumulative total tokens this session |
| `cost_usd` | `message.part.updated` (step-finish) | Cumulative cost in USD this session |
| `tool_name` | `command.executed` / `tool_result` | Last tool/command used |
| `message_count` | `message.updated` | Number of messages exchanged this session |
| `files_modified` | `file.edited` / `file.watcher.updated` | Count of unique files touched |
| `session_duration_ms` | Computed | Time since `session.created` |
| `commits` | `session.diff` | Git commits detected |
| `lines_added` | `session.diff` | Lines added this session |
| `lines_removed` | `session.diff` | Lines removed this session |

## Tamagotchai Configuration

### Multi-agent feed screen

```yaml
screens:
  - name: OpenCode
    template: agent_feed
    poll_interval: 5
    display_duration: 15
    stale_threshold: 120
    agents:
      - name: OpenCode
        url: http://YOUR_AGENT_IP:7788/status
```

The `agent_feed` template displays model name, tokens, and cost inline when available (e.g. `claude-3.7  $0.004`). If no cost data, it falls back to `3 files` or `5 msgs`.

### Single-agent tamagotchi screen

```yaml
screens:
  - name: OpenCode
    template: tamagotchi
    poll_interval: 5
    display_duration: 15
    stale_threshold: 120
    url: http://YOUR_AGENT_IP:7788/status
    sprites:
      idle: img/opencode_idle.png
      working: img/opencode_working.png
      error: img/opencode_error.png
      success: img/opencode_success.png
    mood_map:
      key: status
      map:
        idle: idle
        working: working
        waiting_input: working
        stuck: error
        error: error
        success: success
        offline: error
      fallback: idle
    info_lines:
      - label: status
        key: status
      - label: task
        key: message
        max_length: 18
      - label: model
        key: metadata.model
        max_length: 16
      - label: tokens
        template: "{0} in / {1} out"
        keys: [metadata.tokens_input, metadata.tokens_output]
      - label: cost
        template: "${0}"
        keys: [metadata.cost_usd]
```

## Status Mapping

| OpenCode Event | Tamagotchai Status | Message Example |
|---|---|---|
| `session.created` | `working` | "session started" |
| `command.executed` | `working` | "cmd: bash" |
| `session.diff` | `working` | "applying changes" |
| `message.part.updated` | `working` (preserved) | (previous message) |
| `tool_result` success | `success` | "tool: bash" |
| `tool_result` failure | `error` | "tool failed: bash" |
| `permission.asked` | `waiting_input` | "needs permission: bash" |
| `permission.replied` | `working` | "permission granted" |
| `session.idle` | `idle` | "" |
| `session.error` | `error` | (error text) |
| `session.status: waiting_input` | `waiting_input` | "waiting for input" |
| `session.status: stuck` | `stuck` | "stuck" |

## Development

```bash
cd plugins/opencode-plugin-tamagotchai
npm install
npx tsc --noEmit
```

## License

MIT
