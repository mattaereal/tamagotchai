# pi-tamagotchai

pi extension that writes live session status to JSON files for the
[`tamagotchai-agentd`](../tamagotchai-agentd/) daemon (file backend).
No sockets, no watchers, no timers — files only. Atomic writes
(temp + rename) so the daemon never reads a half-written file.

## State dir

`~/.pi/agent/tamagotchai/sessions/<session-id>.json`

Override with `TAMAGOTCHAI_SESSIONS_DIR` (used by tests).

## What it writes

Each event updates the [Standard Agent Status JSON](../../AGENTS.md#standard-agent-status-json):

| pi event | Effect |
|---|---|
| `session_start` | writes `defaultState` (status `working`, `source: pi`) |
| `before_agent_start` | `working`, message = truncated prompt |
| `tool_execution_start` | `working`, `metadata.tool_name` set |
| `tool_execution_end` | `error` on failure, else `working`; increments `tools_executed` |
| `turn_start` | increments `turn_count` |
| `message_end` | accumulates `tokens_input/output/total` + `cost_usd`; sets `model` |
| `agent_settled` | `idle`, `pending = 0` |
| `session_shutdown` | deletes the file |

Token/cost mapping (pi usage → Standard Agent Status JSON):

| pi `usage` field | metadata field |
|---|---|
| `input` | `tokens_input` |
| `output` | `tokens_output` |
| `totalTokens` | `tokens_total` |
| `cost.total` | `cost_usd` |

The daemon owns staleness — the extension never self-idles. If the extension
process dies, the daemon marks the session `offline` after `stale_threshold`
and drops it after `2 * stale_threshold`.

## Install

    ./plugins/pi-tamagotchai/install.sh
    # then in pi: /reload

This symlinks the plugin into `~/.pi/agent/extensions/pi-tamagotchai` and
creates `~/.pi/agent/tamagotchai/sessions/`.

## Tests

    cd plugins/pi-tamagotchai && npm install && npx vitest run

Unit tests cover the pure state functions (`state.ts`) and the factory wiring
(`index.ts`) via a mock pi runtime that replays events into a temp dir.
