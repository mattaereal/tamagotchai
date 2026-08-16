# pi + hermes Agent Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the e-paper display show live status of pi (this Pi Zero) plus two remote hermes agents, fed by an always-on daemon that keeps port 7788 answering even when no agent session is active.

**Architecture:** A pi extension writes session state to JSON files on disk (no sockets). An always-on Python daemon (`tamagotchai-agentd`) watches those files (file backend, pi host) or receives HMAC-signed webhooks (webhook backend, hermes hosts) and serves Standard Agent Status JSON over HTTP on `0.0.0.0:7788`. The display's existing `agent_feed` screen polls those endpoints via GET only. One daemon per agent host; the display aggregates multiple URLs.

**Tech Stack:** TypeScript (pi extension, loaded via jiti — no compile), Python stdlib `http.server` (daemon), pytest (daemon + display tests), vitest (extension tests), systemd (daemon unit), YAML config (display).

## Spec delta (approved 2026-08-16)

The spec stated "display rendering code stays unchanged." Verification of `core/screens/agent_feed.py:28-30` found the display expects a **dict** per agent URL, but the spec's `screens.yml` pointed at `/status/all` (array). The user's brainstorm answer (Q1: remote + multi-session) requires multi-session visibility. This plan therefore includes one small, backward-compatible display change (Task 7): `agent_feed` expands array responses into multiple rows. Dict responses still render as one row, so existing single-session endpoints keep working. Daemon serves both `/status` (dict) and `/status/all` (array).

## Global Constraints

- Display is GET-only outbound. No inbound port on the display, no POST received by the display.
- Daemon always answers 200 while up; `/status` returns an idle payload when no sessions are live, never connection-refuses.
- The daemon owns staleness. Agents only heartbeat; they never self-idle. Stale (`> stale_threshold`) → `offline`; dead (`> 2 * stale_threshold`) → dropped.
- Standard Agent Status JSON fields: `status` (`idle`|`working`|`waiting_input`|`error`|`success`|`offline`), `message`, `last_heartbeat` (ISO 8601, UTC, with `Z`), `pending`, `metadata` (object).
- pi extension writes files only; starts no sockets, watchers, timers, or processes from the factory. Atomic writes (temp + `os.replace`). Deletes its file on `session_shutdown`.
- Transport is agnostic: tunnels (tailscale / cloudflared) are ops, not code. Daemon binds `0.0.0.0:7788`.
- Display backend stays `mock` on non-Pi dev machines; never change to `waveshare_*` off-device.
- Repo git identity already configured (`mattaereal` / `mattaereal@users.noreply.github.com`).
- Token/cost mapping: pi `usage.input`→`tokens_input`, `usage.output`→`tokens_output`, `usage.totalTokens`→`tokens_total`, `usage.cost.total`→`cost_usd`.
- Hermes webhook events are verified at implementation time against `agent/outbound_webhooks.py`'s registered event list; the mapping table in Task 4 is the minimal set.

---

## File Structure

### New files

```
plugins/tamagotchai-agentd/
├── __init__.py
├── agentd.py                 # Entrypoint: parse args, build registry + backend, serve forever
├── backends/
│   ├── __init__.py
│   ├── file_watch.py         # FileWatchBackend: polls ~/.pi/agent/tamagotchai/sessions/*.json
│   └── webhook.py            # WebhookBackend: /ingest receiver, HMAC-SHA256 verify, hermes event map
├── state.py                  # SessionRegistry: in-memory store, stale sweep, snapshot_all/latest
├── server.py                 # HTTP handler: /health, /status, /status/all, /ingest
├── config.py                 # CLI arg parsing + env defaults
├── agentd.service            # systemd unit template
├── requirements.txt          # (empty or watchdog optional)
└── README.md                 # install/run/systemd docs

plugins/pi-tamagotchai/
├── package.json              # name, pi.extensions entry, devDeps (vitest), no runtime deps
├── tsconfig.json
├── README.md
├── src/
│   ├── state.ts              # Pure functions: buildPayload, applyEvent, atomicWrite, deleteState
│   └── index.ts              # Factory: pi.on(...) → calls state.ts
└── test/
    └── state.test.ts         # vitest unit tests for pure functions

tests/
├── test_agentd_state.py       # SessionRegistry + stale sweep
├── test_agentd_server.py      # /health, /status, /status/all
├── test_agentd_file_watch.py  # file backend
├── test_agentd_webhook.py     # /ingest HMAC + hermes event map
└── test_agent_feed_array.py   # display agent_feed array expansion
```

### Modified files

```
core/screens/agent_feed.py    # _fetch_agent returns list[dict]; fetch() flattens (backward compat)
config/screens.yml.example    # replace dead opencode screen with agent_feed pulling real hosts
config/screens.yml            # same (live config; gitignored)
```

### Import-path note

`plugins/tamagotchai-agentd/` has a hyphen, so Python cannot import it as a normal package name. The plan adds a repo-root `conftest.py` (Task 1, Step 3) that inserts `plugins/` onto `sys.path`; modules then import as `from tamagotchai_agentd.state import SessionRegistry`. All test imports in this plan use the `tamagotchai_agentd.<module>` form (no `plugins.` prefix).

---

## Task 1: Daemon SessionRegistry + stale sweep

**Files:**
- Create: `plugins/tamagotchai-agentd/__init__.py`
- Create: `plugins/tamagotchai-agentd/state.py`
- Create/modify: `conftest.py` (repo root)
- Test: `tests/test_agentd_state.py`

**Interfaces:**
- Consumes: nothing (leaf module)
- Produces: `SessionRegistry` class:
  - `update(session_id: str, payload: dict) -> None` — upsert; `payload` is a Standard Agent Status JSON dict (must contain `last_heartbeat` ISO 8601 string)
  - `remove(session_id: str) -> None` — delete entry
  - `sweep(stale_secs: int, now: datetime) -> None` — entries older than `stale_secs` → `status="offline"`; older than `2 * stale_secs` → dropped
  - `snapshot_all() -> list[dict]` — all live entries sorted by `last_heartbeat` desc; each dict has `session_id` injected
  - `latest() -> dict` — most recent live entry, or the idle payload `{"status":"idle","message":"no sessions","last_heartbeat":<now iso>,"pending":0,"metadata":{}}` if none

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentd_state.py
from datetime import datetime, timedelta, timezone

from tamagotchai_agentd.state import SessionRegistry


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_update_and_snapshot_all_returns_entries_sorted_by_heartbeat_desc():
    reg = SessionRegistry()
    old = datetime(2026, 8, 16, 10, 0, 0, tzinfo=timezone.utc)
    new = datetime(2026, 8, 16, 10, 5, 0, tzinfo=timezone.utc)
    reg.update("s1", {"status": "working", "last_heartbeat": _iso(old), "metadata": {}})
    reg.update("s2", {"status": "working", "last_heartbeat": _iso(new), "metadata": {}})
    snap = reg.snapshot_all()
    assert [e["session_id"] for e in snap] == ["s2", "s1"]


def test_latest_returns_idle_payload_when_empty():
    reg = SessionRegistry()
    latest = reg.latest()
    assert latest["status"] == "idle"
    assert latest["message"] == "no sessions"
    assert latest["pending"] == 0
    assert latest["metadata"] == {}


def test_sweep_marks_offline_after_stale_secs():
    reg = SessionRegistry()
    now = datetime(2026, 8, 16, 10, 5, 0, tzinfo=timezone.utc)
    old = now - timedelta(seconds=200)
    reg.update("s1", {"status": "working", "last_heartbeat": _iso(old), "metadata": {}})
    reg.sweep(stale_secs=120, now=now)
    snap = reg.snapshot_all()
    assert snap[0]["status"] == "offline"


def test_sweep_drops_entries_older_than_2x_stale_secs():
    reg = SessionRegistry()
    now = datetime(2026, 8, 16, 10, 5, 0, tzinfo=timezone.utc)
    dead = now - timedelta(seconds=300)
    reg.update("s1", {"status": "working", "last_heartbeat": _iso(dead), "metadata": {}})
    reg.sweep(stale_secs=120, now=now)
    assert reg.snapshot_all() == []


def test_remove_deletes_entry():
    reg = SessionRegistry()
    reg.update("s1", {"status": "working", "last_heartbeat": _iso(datetime.now(timezone.utc)), "metadata": {}})
    reg.remove("s1")
    assert reg.snapshot_all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agentd_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tamagotchai_agentd'`

- [ ] **Step 3: Write minimal implementation**

First check for an existing `conftest.py` at repo root. If it exists, append the `sys.path` insert below to it; if not, create it:

```python
# conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "plugins"))
```

```python
# plugins/tamagotchai-agentd/__init__.py
# empty
```

```python
# plugins/tamagotchai-agentd/state.py
"""In-memory session registry with stale sweep. Owns staleness for the display."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def _parse_heartbeat(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class _Entry:
    session_id: str
    payload: dict = field(default_factory=dict)
    heartbeat: Optional[datetime] = None


class SessionRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, _Entry] = {}

    def update(self, session_id: str, payload: dict) -> None:
        hb = _parse_heartbeat(payload.get("last_heartbeat", ""))
        self._entries[session_id] = _Entry(
            session_id=session_id,
            payload=dict(payload),
            heartbeat=hb,
        )
        self._entries[session_id].payload["session_id"] = session_id

    def remove(self, session_id: str) -> None:
        self._entries.pop(session_id, None)

    def sweep(self, stale_secs: int, now: datetime) -> None:
        stale_at = now - timedelta(seconds=stale_secs)
        dead_at = now - timedelta(seconds=2 * stale_secs)
        for sid, e in list(self._entries.items()):
            if e.heartbeat is None:
                continue
            if e.heartbeat < dead_at:
                self._entries.pop(sid, None)
            elif e.heartbeat < stale_at:
                e.payload["status"] = "offline"

    def snapshot_all(self) -> List[dict]:
        live = [e for e in self._entries.values() if e.heartbeat is not None]
        live.sort(key=lambda e: e.heartbeat, reverse=True)
        return [dict(e.payload) for e in live]

    def latest(self) -> dict:
        snap = self.snapshot_all()
        if snap:
            return snap[0]
        return {
            "status": "idle",
            "message": "no sessions",
            "last_heartbeat": _now_iso(),
            "pending": 0,
            "metadata": {},
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_state.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add conftest.py plugins/tamagotchai-agentd/__init__.py plugins/tamagotchai-agentd/state.py tests/test_agentd_state.py
git commit -m "feat(agentd): SessionRegistry with stale sweep"
```

---

## Task 2: Daemon HTTP server (/health, /status, /status/all)

**Files:**
- Create: `plugins/tamagotchai-agentd/server.py`
- Test: `tests/test_agentd_server.py`

**Interfaces:**
- Consumes: `SessionRegistry` from `state.py` (Task 1)
- Produces: `make_handler(registry: SessionRegistry, webhook_backend=None) -> type` — returns a `http.server.BaseHTTPRequestHandler` subclass:
  - `GET /health` → `200` body `ok`
  - `GET /status` → `200` JSON `registry.latest()`
  - `GET /status/all` → `200` JSON array `registry.snapshot_all()`
  - `POST /ingest` → delegated to `webhook_backend.handle(body: bytes, headers: dict) -> int` if set (Task 4); else `404`
  - Any other path → `404`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentd_server.py
import json
from http.server import HTTPServer
from threading import Thread
from urllib import request

from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.server import make_handler


def _start_server(registry, webhook_backend=None):
    handler = make_handler(registry, webhook_backend=webhook_backend)
    srv = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    log.info("tamagotchai-agentd listening on %s:%d (backend=%s)", cfg.host, cfg.port, cfg.backend)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_config.py -v`
Expected: PASS (2 tests)

Manually smoke-test the daemon end-to-end:
```bash
python plugins/tamagotchai-agentd/agentd.py --backend file --port 7788 &
curl -s http://127.0.0.1:7788/health   # -> ok
curl -s http://127.0.0.1:7788/status   # -> idle payload
curl -s http://127.0.0.1:7788/status/all  # -> []
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/config.py plugins/tamagotchai-agentd/agentd.py tests/test_agentd_config.py
git commit -m "feat(agentd): entrypoint, config, stale-sweep loop"
```

---

### systemd unit

Create `plugins/tamagotchai-agentd/agentd.service`:

```ini
[Unit]
Description=tamagotchai status daemon (always-on agent /status server)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h
Environment=TAMAGOTCHAI_BACKEND=file
Environment=TAMAGOTCHAI_PORT=7788
Environment=TAMAGOTCHAI_STALE_SECS=120
# For hermes hosts, set backend=webhook and set HERMES_WEBHOOK_SECRET in an EnvironmentFile.
ExecStart=/usr/bin/python3 %h/tamagotchai/plugins/tamagotchai-agentd/agentd.py
Restart=always
RestartSec=3
User=%i

[Install]
WantedBy=default.target
```

Install: `sudo cp plugins/tamagotchai-agentd/agentd.service /etc/systemd/system/tamagotchai-agentd@.service && sudo systemctl enable --now tamagotchai-agentd@senpai`

Create `plugins/tamagotchai-agentd/requirements.txt` (empty — stdlib only):

```
# no runtime deps; watchdog optional (not used by the polling backend)
```

Create `plugins/tamagotchai-agentd/README.md` documenting: install, two backends, env vars, systemd, cloudflared/tailscale exposure. Content:

```markdown
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

    python agentd.py --backend file --port 7788

Env overrides: `TAMAGOTCHAI_BACKEND`, `TAMAGOTCHAI_HOST`, `TAMAGOTCHAI_PORT`,
`TAMAGOTCHAI_SESSIONS_DIR`, `TAMAGOTCHAI_STALE_SECS`, `TAMAGOTCHAI_POLL_INTERVAL`,
`HERMES_WEBHOOK_SECRET`.

## systemd

    sudo cp agentd.service /etc/systemd/system/tamagotchai-agentd@.service
    sudo systemctl enable --now tamagotchai-agentd@<user>

## Transport

Bind is 0.0.0.0:7788. Reach it via tailscale or cloudflared. The daemon is
transport-agnostic — no tunnel code here.
```

```bash
git add plugins/tamagotchai-agentd/agentd.service plugins/tamagotchai-agentd/requirements.txt plugins/tamagotchai-agentd/README.md
git commit -m "feat(agentd): systemd unit + README"
```
=webhook_backend)
    srv = HTTPServer(("127.0.0.1", 0), handler)
    Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _get(port, path):
    with request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, r.read().decode()


def test_health_returns_200_ok():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/health")
    srv.shutdown()
    assert body == "ok"


def test_status_returns_idle_when_empty():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/status")
    srv.shutdown()
    data = json.loads(body)
    assert data["status"] == "idle"
    assert data["message"] == "no sessions"


def test_status_all_returns_array():
    srv = _start_server(SessionRegistry())
    _, body = _get(srv.server_address[1], "/status/all")
    srv.shutdown()
    assert json.loads(body) == []


def test_status_all_returns_registered_sessions():
    from datetime import datetime, timezone
    reg = SessionRegistry()
    now = datetime(2026, 8, 16, 10, 5, 0, tzinfo=timezone.utc)
    reg.update("s1", {"status": "working", "last_heartbeat": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "metadata": {}})
    srv = _start_server(reg)
    _, body = _get(srv.server_address[1], "/status/all")
    srv.shutdown()
    arr = json.loads(body)
    assert len(arr) == 1
    assert arr[0]["session_id"] == "s1"


def test_unknown_path_returns_404():
    srv = _start_server(SessionRegistry())
    try:
        _get(srv.server_address[1], "/nope")
    except request.HTTPError as e:
        assert e.code == 404
    srv.shutdown()


def test_ingest_returns_404_without_webhook_backend():
    srv = _start_server(SessionRegistry())
    try:
        req = request.Request(f"http://127.0.0.1:{srv.server_address[1]}/ingest", method="POST")
        request.urlopen(req, timeout=5)
    except request.HTTPError as e:
        assert e.code == 404
    srv.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agentd_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tamagotchai_agentd.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/tamagotchai-agentd/server.py
"""HTTP server: /health, /status, /status/all, /ingest."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler

from .state import SessionRegistry


def make_handler(registry: SessionRegistry, webhook_backend=None):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body=b"", content_type="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _send_json(self, code, obj):
            self._send(code, json.dumps(obj).encode(), content_type="application/json")

        def do_GET(self):
            if self.path == "/health":
                self._send(200, b"ok")
            elif self.path == "/status":
                self._send_json(200, registry.latest())
            elif self.path == "/status/all":
                self._send_json(200, registry.snapshot_all())
            else:
                self._send(404, b"not found")

        def do_POST(self):
            if self.path == "/ingest" and webhook_backend is not None:
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length else b""
                code = webhook_backend.handle(body, {k: v for k, v in self.headers.items()})
                self._send(code, b"" if 200 <= code < 300 else b"error")
            else:
                self._send(404, b"not found")

        def log_message(self, *args, **kwargs):
            pass  # quiet; agentd.py wires real logging

    return Handler
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_server.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/server.py tests/test_agentd_server.py
git commit -m "feat(agentd): HTTP server /health /status /status/all"
```

---

## Task 3: Daemon file backend (polls sessions dir)

**Files:**
- Create: `plugins/tamagotchai-agentd/backends/__init__.py`
- Create: `plugins/tamagotchai-agentd/backends/file_watch.py`
- Test: `tests/test_agentd_file_watch.py`

**Interfaces:**
- Consumes: `SessionRegistry` from `state.py` (Task 1)
- Produces: `FileWatchBackend` class:
  - `__init__(self, registry: SessionRegistry, sessions_dir: str)` — stores dir; does NOT start a watcher (the entrypoint drives polling)
  - `poll(self) -> None` — re-reads `sessions_dir/*.json`, calls `registry.update(session_id, payload)` for each present file and `registry.remove(session_id)` for each previously-seen session id whose file is gone. Malformed JSON → log warning, skip (do not crash). Each file's JSON must contain `session_id`; if missing, derive from the filename stem.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentd_file_watch.py
import json
from pathlib import Path

from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.backends.file_watch import FileWatchBackend


def _write_session(tmp_path: Path, sid: str, payload: dict) -> None:
    p = tmp_path / f"{sid}.json"
    p.write_text(json.dumps(payload))


def test_poll_reads_present_files_into_registry():
    reg = SessionRegistry()
    be = FileWatchBackend(reg, "/tmp/does-not-matter")
    d = Path("/tmp/does-not-matter")
    d.mkdir(exist_ok=True)
    _write_session(d, "s1", {"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}, "session_id": "s1"})
    be.poll()
    snap = reg.snapshot_all()
    assert len(snap) == 1
    assert snap[0]["session_id"] == "s1"


def test_poll_uses_filename_stem_when_session_id_missing(tmp_path):
    reg = SessionRegistry()
    be = FileWatchBackend(reg, str(tmp_path))
    (tmp_path / "abc.json").write_text(json.dumps({"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}}))
    be.poll()
    snap = reg.snapshot_all()
    assert snap[0]["session_id"] == "abc"


def test_poll_removes_registry_entry_when_file_deleted(tmp_path):
    reg = SessionRegistry()
    be = FileWatchBackend(reg, str(tmp_path))
    _write_session(tmp_path, "s1", {"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}, "session_id": "s1"})
    be.poll()
    assert len(reg.snapshot_all()) == 1
    (tmp_path / "s1.json").unlink()
    be.poll()
    assert reg.snapshot_all() == []


def test_poll_skips_malformed_json_without_crashing(tmp_path, caplog):
    reg = SessionRegistry()
    be = FileWatchBackend(reg, str(tmp_path))
    (tmp_path / "bad.json").write_text("{not json")
    (tmp_path / "good.json").write_text(json.dumps({"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}, "session_id": "good"}))
    be.poll()
    snap = reg.snapshot_all()
    assert [e["session_id"] for e in snap] == ["good"]


def test_poll_ignores_non_json_files(tmp_path):
    reg = SessionRegistry()
    be = FileWatchBackend(reg, str(tmp_path))
    (tmp_path / "s1.txt").write_text("ignore me")
    be.poll()
    assert reg.snapshot_all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agentd_file_watch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tamagotchai_agentd.backends'`

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/tamagotchai-agentd/backends/__init__.py
# empty
```

```python
# plugins/tamagotchai-agentd/backends/file_watch.py
"""File backend: polls ~/.pi/agent/tamagotchai/sessions/*.json into the registry."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..state import SessionRegistry

logger = logging.getLogger(__name__)


class FileWatchBackend:
    def __init__(self, registry: SessionRegistry, sessions_dir: str) -> None:
        self._registry = registry
        self._dir = Path(sessions_dir)
        self._seen: set[str] = set()

    def poll(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        present_ids: set[str] = set()
        for p in self._dir.glob("*.json"):
            try:
                payload = json.loads(p.read_text())
                if not isinstance(payload, dict):
                    logger.warning("ignoring non-object file %s", p)
                    continue
                sid = payload.get("session_id") or p.stem
                self._registry.update(sid, payload)
                present_ids.add(sid)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("malformed session file %s: %s", p, e)
                continue
        for sid in self._seen - present_ids:
            self._registry.remove(sid)
        self._seen = present_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_file_watch.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/backends/__init__.py plugins/tamagotchai-agentd/backends/file_watch.py tests/test_agentd_file_watch.py
git commit -m "feat(agentd): file-watch backend polling sessions dir"
```

---

## Task 4: Daemon webhook backend + /ingest (HMAC)

**Files:**
- Create: `plugins/tamagotchai-agentd/backends/webhook.py`
- Test: `tests/test_agentd_webhook.py`

**Interfaces:**
- Consumes: `SessionRegistry` from `state.py` (Task 1)
- Produces: `WebhookBackend` class:
  - `__init__(self, registry: SessionRegistry, secret: str | None)`
  - `handle(self, body: bytes, headers: dict) -> int` — verifies HMAC-SHA256 of body against `secret` (GitHub-style `sha256=<hex>` in `X-Hermes-Signature-256` header). Missing secret config → accept unsigned (dev mode). Bad signature → `401`. Valid → translate hermes event to Standard Agent Status JSON, `registry.update(session_id, payload)`, return `204`. Malformed JSON → `400`.
  - Exposes `map_event(event_name: str, payload: dict) -> tuple[str, dict] | None` (pure, separately testable) returning `(session_id, status_payload)`. Returns `None` for events that don't change status.

**Hermes webhook → status mapping** (minimal; verify exact event names against `agent/outbound_webhooks.py` at implementation time — the payload always includes `session_id`, `tool_name`, `tool_input`, `extra`, `hook_event_name`, `timestamp`):

| hermes hook event | status | message | metadata |
|---|---|---|---|
| `on_session_start` (or first event for a `session_id`) | `working` | `session started` | register session; `source: hermes` |
| `pre_tool_call` | `working` | `tool: <tool_name>` | `tool_name` |
| `post_tool_call` | `success` (no error) / `error` | `tool: <tool_name>` | `tools_executed`++ |
| `on_message` (if emitted; else `message_end`) | `working` | — | accumulate tokens/cost/model from `extra` if present |
| `on_session_end` | `idle` | `ended` | then expire via stale sweep |
| `subagent_stop` | `working` | — | `subagents_done`++ (parent still active) |

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentd_webhook.py
import hashlib
import hmac
import json
from datetime import datetime, timezone

from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.backends.webhook import WebhookBackend


def _sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(event_name: str, session_id: str = "s1", extra: dict | None = None, tool: str | None = None) -> bytes:
    payload = {
        "hook_event_name": event_name,
        "session_id": session_id,
        "tool_name": tool,
        "tool_input": None,
        "cwd": "/home/u/proj",
        "extra": extra or {},
        "delivery_id": "d1",
        "timestamp": "2026-08-16T10:00:00Z",
    }
    return json.dumps(payload).encode()


def test_map_event_pre_tool_call_returns_working():
    body = _post("pre_tool_call", tool="bash")
    payload = json.loads(body)
    out = WebhookBackend(SessionRegistry(), secret=None).map_event("pre_tool_call", payload)
    assert out is not None
    sid, state = out
    assert sid == "s1"
    assert state["status"] == "working"
    assert state["message"] == "tool: bash"
    assert state["metadata"]["tool_name"] == "bash"


def test_map_event_unknown_returns_none():
    out = WebhookBackend(SessionRegistry(), secret=None).map_event("some_other_event", {"session_id": "s1"})
    assert out is None


def test_handle_valid_signature_updates_registry():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret="shh")
    body = _post("pre_tool_call", tool="bash")
    code = be.handle(body, {"X-Hermes-Signature-256": _sig("shh", body)})
    assert code == 204
    snap = reg.snapshot_all()
    assert len(snap) == 1
    assert snap[0]["status"] == "working"


def test_handle_bad_signature_returns_401():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret="shh")
    body = _post("pre_tool_call", tool="bash")
    code = be.handle(body, {"X-Hermes-Signature-256": "sha256=deadbeef"})
    assert code == 401
    assert reg.snapshot_all() == []


def test_handle_missing_signature_when_secret_set_returns_401():
    be = WebhookBackend(SessionRegistry(), secret="shh")
    body = _post("pre_tool_call")
    assert be.handle(body, {}) == 401


def test_handle_accepts_unsigned_when_no_secret():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret=None)
    body = _post("pre_tool_call", tool="bash")
    assert be.handle(body, {}) == 204
    assert len(reg.snapshot_all()) == 1


def test_handle_malformed_json_returns_400():
    be = WebhookBackend(SessionRegistry(), secret=None)
    assert be.handle(b"{not json", {}) == 400


def test_handle_on_session_end_marks_idle():
    reg = SessionRegistry()
    be = WebhookBackend(reg, secret=None)
    body = _post("on_session_end")
    code = be.handle(body, {})
    assert code == 204
    snap = reg.snapshot_all()
    assert snap[0]["status"] == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agentd_webhook.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tamagotchai_agentd.backends.webhook'`

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/tamagotchai-agentd/backends/webhook.py
"""Webhook backend: /ingest receiver with HMAC-SHA256 verify + hermes event map."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from ..state import SessionRegistry

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Per-session accumulated counters (tokens/cost/tools). In-memory; rebuilt on restart.
_acc: dict[str, dict] = {}


def _acc_init(sid: str) -> dict:
    return _acc.setdefault(sid, {
        "tokens_input": 0, "tokens_output": 0, "tokens_total": 0,
        "cost_usd": 0.0, "tools_executed": 0, "subagents_done": 0,
        "model": None, "project": None,
    })


class WebhookBackend:
    def __init__(self, registry: SessionRegistry, secret: Optional[str]) -> None:
        self._registry = registry
        self._secret = secret

    def map_event(self, event_name: str, payload: dict) -> Optional[Tuple[str, dict]]:
        sid = payload.get("session_id")
        if not sid:
            return None
        tool = payload.get("tool_name")
        extra = payload.get("extra") or {}
        cwd = payload.get("cwd") or ""
        acc = _acc_init(sid)
        if cwd:
            acc["project"] = cwd.rsplit("/", 1)[-1] or cwd

        def base(status: str, message: str) -> dict:
            return {
                "status": status,
                "message": message,
                "last_heartbeat": _now_iso(),
                "pending": 1 if status == "working" else 0,
                "metadata": {
                    "source": "hermes",
                    "project": acc["project"],
                    "model": acc.get("model"),
                    "tool_name": tool,
                    "tokens_input": acc["tokens_input"],
                    "tokens_output": acc["tokens_output"],
                    "tokens_total": acc["tokens_total"],
                    "cost_usd": round(acc["cost_usd"], 4),
                    "tools_executed": acc["tools_executed"],
                    "subagents_done": acc["subagents_done"],
                },
            }

        if event_name in ("on_session_start", "session_start"):
            return sid, base("working", "session started")
        if event_name == "pre_tool_call":
            return sid, base("working", f"tool: {tool}" if tool else "tool: ?")
        if event_name == "post_tool_call":
            acc["tools_executed"] += 1
            err = bool(extra.get("error") or extra.get("is_error"))
            status = "error" if err else "success"
            return sid, base(status, f"tool: {tool}" if tool else "tool: ?")
        if event_name in ("on_message", "message_end"):
            u = extra.get("usage") or {}
            if isinstance(u, dict):
                acc["tokens_input"] += int(u.get("input", 0) or 0)
                acc["tokens_output"] += int(u.get("output", 0) or 0)
                acc["tokens_total"] += int(u.get("totalTokens", 0) or 0)
                cost = u.get("cost")
                if isinstance(cost, dict):
                    acc["cost_usd"] += float(cost.get("total", 0) or 0)
            m = extra.get("model")
            if m:
                acc["model"] = m
            return sid, base("working", "")
        if event_name == "on_session_end":
            return sid, base("idle", "ended")
        if event_name == "subagent_stop":
            acc["subagents_done"] += 1
            return sid, base("working", "")
        return None

    def _verify(self, body: bytes, headers: dict) -> bool:
        if not self._secret:
            return True  # dev mode: unsigned accepted
        sig = headers.get("X-Hermes-Signature-256") or headers.get("x-hermes-signature-256")
        if not sig:
            return False
        expected = "sha256=" + hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def handle(self, body: bytes, headers: dict) -> int:
        if self._secret and not self._verify(body, headers):
            return 401
        try:
            payload = json.loads(body.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400
        if not isinstance(payload, dict):
            return 400
        event_name = payload.get("hook_event_name") or payload.get("type")
        if not event_name:
            return 400
        mapped = self.map_event(event_name, payload)
        if mapped is None:
            return 204  # event observed, no state change
        sid, state = mapped
        self._registry.update(sid, state)
        return 204
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_webhook.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/backends/webhook.py tests/test_agentd_webhook.py
git commit -m "feat(agentd): webhook backend with HMAC + hermes event map"
```

---

## Task 5: Daemon entrypoint, config, stale-sweep loop, systemd unit

**Files:**
- Create: `plugins/tamagotchai-agentd/config.py`
- Create: `plugins/tamagotchai-agentd/agentd.py`
- Create: `plugins/tamagotchai-agentd/agentd.service`
- Create: `plugins/tamagotchai-agentd/requirements.txt`
- Create: `plugins/tamagotchai-agentd/README.md`

**Interfaces:**
- Consumes: `SessionRegistry` (Task 1), `make_handler` (Task 2), `FileWatchBackend` (Task 3), `WebhookBackend` (Task 4)
- Produces: runnable `python plugins/tamagotchai-agentd/agentd.py` with CLI:
  - `--backend {file,webhook}` (env `TAMAGOTCHAI_BACKEND`, default `file`)
  - `--host` (env `TAMAGOTCHAI_HOST`, default `0.0.0.0`)
  - `--port` (env `TAMAGOTCHAI_PORT`, default `7788`)
  - `--sessions-dir` (env `TAMAGOTCHAI_SESSIONS_DIR`, default `~/.pi/agent/tamagotchai/sessions`)
  - `--stale-secs` (env `TAMAGOTCHAI_STALE_SECS`, default `120`)
  - `--secret` (env `HERMES_WEBHOOK_SECRET`, default unset)
  - `--poll-interval` (env `TAMAGOTCHAI_POLL_INTERVAL`, default `1`) for file backend
- Behavior: build registry + backend (file: poll loop in a daemon thread; webhook: pass backend to `make_handler`). Stale-sweep thread runs every `max(1, stale_secs // 2)` seconds. HTTP server runs in main thread.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agentd_config.py
import importlib.util
from pathlib import Path

def test_config_defaults():
    spec = importlib.util.spec_from_file_location("agentd_config", "plugins/tamagotchai-agentd/config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = mod.parse_args(["--backend", "file"])
    assert cfg.backend == "file"
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 7788
    assert cfg.stale_secs == 120
    assert cfg.poll_interval == 1

def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("TAMAGOTCHAI_PORT", "9999")
    monkeypatch.setenv("TAMAGOTCHAI_BACKEND", "webhook")
    monkeypatch.setenv("HERMES_WEBHOOK_SECRET", "s")
    spec = importlib.util.spec_from_file_location("agentd_config2", "plugins/tamagotchai-agentd/config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cfg = mod.parse_args([])
    assert cfg.port == 9999
    assert cfg.backend == "webhook"
    assert cfg.secret == "s"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agentd_config.py -v`
Expected: FAIL (no config.py)

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/tamagotchai-agentd/config.py
from __future__ import annotations
import argparse
import os
from dataclasses import dataclass


@dataclass
class Config:
    backend: str
    host: str
    port: int
    sessions_dir: str
    stale_secs: int
    poll_interval: int
    secret: str | None


def parse_args(argv: list[str]) -> Config:
    p = argparse.ArgumentParser(prog="tamagotchai-agentd")
    p.add_argument("--backend", default=os.environ.get("TAMAGOTCHAI_BACKEND", "file"))
    p.add_argument("--host", default=os.environ.get("TAMAGOTCHAI_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("TAMAGOTCHAI_PORT", "7788")))
    p.add_argument("--sessions-dir", default=os.environ.get("TAMAGOTCHAI_SESSIONS_DIR",
                                                            os.path.expanduser("~/.pi/agent/tamagotchai/sessions")))
    p.add_argument("--stale-secs", type=int, default=int(os.environ.get("TAMAGOTCHAI_STALE_SECS", "120")))
    p.add_argument("--poll-interval", type=int, default=int(os.environ.get("TAMAGOTCHAI_POLL_INTERVAL", "1")))
    p.add_argument("--secret", default=os.environ.get("HERMES_WEBHOOK_SECRET"))
    a = p.parse_args(argv)
    return Config(a.backend, a.host, a.port, a.sessions_dir, a.stale_secs, a.poll_interval, a.secret)
```

```python
# plugins/tamagotchai-agentd/agentd.py
"""tamagotchai-agentd: always-on status daemon for the e-paper display."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

from .config import parse_args
from .state import SessionRegistry
from .server import make_handler
from .backends.file_watch import FileWatchBackend
from .backends.webhook import WebhookBackend

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("tamagotchai-agentd")


def main(argv: list[str] | None = None) -> None:
    cfg = parse_args(argv if argv is not None else None)
    registry = SessionRegistry()
    webhook_backend = None

    if cfg.backend == "file":
        fb = FileWatchBackend(registry, cfg.sessions_dir)
        def _file_loop():
            while True:
                try:
                    fb.poll()
                except Exception as e:
                    log.warning("file poll error: %s", e)
                time.sleep(cfg.poll_interval)
        threading.Thread(target=_file_loop, daemon=True).start()
    elif cfg.backend == "webhook":
        webhook_backend = WebhookBackend(registry, secret=cfg.secret)
    else:
        raise SystemExit(f"unknown backend: {cfg.backend}")

    def _sweep_loop():
        interval = max(1, cfg.stale_secs // 2)
        while True:
            time.sleep(interval)
            registry.sweep(cfg.stale_secs, datetime.now(timezone.utc))
    threading.Thread(target=_sweep_loop, daemon=True).start()

    handler = make_handler(registry, webhook_backend=webhook_backend)
    srv = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    log.info("tamagotchai-agentd listening on %s:%d (backend=%s)", cfg.host, cfg.port, cfg.backend)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agentd_config.py -v`
Expected: PASS (2 tests)

Manually smoke-test the daemon end-to-end:
```bash
python plugins/tamagotchai-agentd/agentd.py --backend file --port 7788 &
curl -s http://127.0.0.1:7788/health   # -> ok
curl -s http://127.0.0.1:7788/status   # -> idle payload
curl -s http://127.0.0.1:7788/status/all  # -> []
kill %1
```

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/config.py plugins/tamagotchai-agentd/agentd.py tests/test_agentd_config.py
git commit -m "feat(agentd): entrypoint, config, stale-sweep loop"
```

---

### systemd unit

Create `plugins/tamagotchai-agentd/agentd.service`:

```ini
[Unit]
Description=tamagotchai status daemon (always-on agent /status server)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h
Environment=TAMAGOTCHAI_BACKEND=file
Environment=TAMAGOTCHAI_PORT=7788
Environment=TAMAGOTCHAI_STALE_SECS=120
# For hermes hosts, set backend=webhook and set HERMES_WEBHOOK_SECRET in an EnvironmentFile.
ExecStart=/usr/bin/python3 %h/tamagotchai/plugins/tamagotchai-agentd/agentd.py
Restart=always
RestartSec=3
User=%i

[Install]
WantedBy=default.target
```

Install: `sudo cp plugins/tamagotchai-agentd/agentd.service /etc/systemd/system/tamagotchai-agentd@.service && sudo systemctl enable --now tamagotchai-agentd@senpai`

Create `plugins/tamagotchai-agentd/requirements.txt` (empty — stdlib only):

```
# no runtime deps; watchdog optional (not used by the polling backend)
```

Create `plugins/tamagotchai-agentd/README.md` documenting: install, two backends, env vars, systemd, cloudflared/tailscale exposure. Content:

```markdown
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

    python agentd.py --backend file --port 7788

Env overrides: `TAMAGOTCHAI_BACKEND`, `TAMAGOTCHAI_HOST`, `TAMAGOTCHAI_PORT`,
`TAMAGOTCHAI_SESSIONS_DIR`, `TAMAGOTCHAI_STALE_SECS`, `TAMAGOTCHAI_POLL_INTERVAL`,
`HERMES_WEBHOOK_SECRET`.

## systemd

    sudo cp agentd.service /etc/systemd/system/tamagotchai-agentd@.service
    sudo systemctl enable --now tamagotchai-agentd@<user>

## Transport

Bind is 0.0.0.0:7788. Reach it via tailscale or cloudflared. The daemon is
transport-agnostic — no tunnel code here.
```

```bash
git add plugins/tamagotchai-agentd/agentd.service plugins/tamagotchai-agentd/requirements.txt plugins/tamagotchai-agentd/README.md
git commit -m "feat(agentd): systemd unit + README"
```


---

## Task 6: pi extension scaffold + pure state functions

**Files:**
- Create: `plugins/pi-tamagotchai/package.json`
- Create: `plugins/pi-tamagotchai/tsconfig.json`
- Create: `plugins/pi-tamagotchai/src/state.ts`
- Create: `plugins/pi-tamagotchai/test/state.test.ts`
- Create: `plugins/pi-tamagotchai/README.md`

**Interfaces:**
- Produces (pure functions in `src/state.ts`, all testable without the pi runtime):
  - `interface AgentState { status: string; message: string; last_heartbeat: string; pending: number; metadata: { project?: string; model?: string; tool_name?: string; turn_count?: number; tools_executed?: number; tokens_input?: number; tokens_output?: number; tokens_total?: number; cost_usd?: number; session_duration_ms?: number; source: "pi" }; }`
  - `defaultState(project: string): AgentState`
  - `applyEvent(state: AgentState, event: { type: string; [k: string]: any }, ctx: { cwd?: string; model?: { provider?: string; id?: string } }): AgentState` — returns a NEW state (immutable). Handles event types `session_start`, `before_agent_start`, `tool_execution_start`, `tool_execution_end`, `turn_start`, `turn_end`, `message_end`, `agent_settled`. Returns `state` unchanged for unknown events.
  - `extractUsage(message: any): { tokens_input: number; tokens_output: number; tokens_total: number; cost_usd: number } | null`
  - `stateFilePath(sessionsDir: string, sessionId: string): string`
  - `atomicWrite(path: string, state: AgentState): void` — write `.tmp` then `fs.renameSync`
  - `deleteState(path: string): void` — `fs.unlinkSync`, swallow ENOENT

- [ ] **Step 1: Write the failing test**

```typescript
// plugins/pi-tamagotchai/test/state.test.ts
import { describe, it, expect } from "vitest";
import { applyEvent, defaultState, extractUsage, stateFilePath } from "../src/state";

describe("defaultState", () => {
  it("starts working with source pi", () => {
    const s = defaultState("tamagotchai");
    expect(s.status).toBe("working");
    expect(s.message).toBe("session started");
    expect(s.metadata.source).toBe("pi");
    expect(s.metadata.project).toBe("tamagotchai");
  });
});

describe("applyEvent", () => {
  it("tool_execution_start sets working + tool_name + message", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    expect(out.status).toBe("working");
    expect(out.message).toBe("tool: bash");
    expect(out.metadata.tool_name).toBe("bash");
  });

  it("tool_execution_end error sets status error", () => {
    const s = defaultState("p");
    const mid = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    const out = applyEvent(mid, { type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: true }, {});
    expect(out.status).toBe("error");
    expect(out.metadata.tools_executed).toBe(1);
  });

  it("tool_execution_end success keeps working and counts", () => {
    const s = defaultState("p");
    const mid = applyEvent(s, { type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, {});
    const out = applyEvent(mid, { type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: false }, {});
    expect(out.status).toBe("working");
    expect(out.metadata.tools_executed).toBe(1);
  });

  it("turn_start increments turn_count", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "turn_start", turnIndex: 0, timestamp: 0 }, {});
    expect(out.metadata.turn_count).toBe(1);
  });

  it("agent_settled sets idle", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "agent_settled" }, {});
    expect(out.status).toBe("idle");
    expect(out.message).toBe("settled");
  });

  it("message_end accumulates usage and model", () => {
    let s = defaultState("p");
    s = applyEvent(s, { type: "message_end", message: { role: "assistant", usage: { input: 10, output: 5, totalTokens: 15, cost: { total: 0.01 } } } }, { model: { provider: "anthropic", id: "claude-3.7-sonnet" } });
    expect(s.metadata.tokens_input).toBe(10);
    expect(s.metadata.tokens_output).toBe(5);
    expect(s.metadata.tokens_total).toBe(15);
    expect(s.metadata.cost_usd).toBe(0.01);
    expect(s.metadata.model).toBe("anthropic/claude-3.7-sonnet");
  });

  it("before_agent_start truncates prompt into message", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "before_agent_start", prompt: "x".repeat(80) }, {});
    expect(out.message.length).toBeLessThanOrEqual(60);
  });

  it("unknown event returns state unchanged", () => {
    const s = defaultState("p");
    const out = applyEvent(s, { type: "whatever" }, {});
    expect(out).toBe(s);
  });
});

describe("extractUsage", () => {
  it("returns null when no usage", () => {
    expect(extractUsage({ role: "assistant" })).toBeNull();
  });
  it("maps fields", () => {
    const u = extractUsage({ usage: { input: 1, output: 2, totalTokens: 3, cost: { total: 0.5 } } });
    expect(u).toEqual({ tokens_input: 1, tokens_output: 2, tokens_total: 3, cost_usd: 0.5 });
  });
});

describe("stateFilePath", () => {
  it("joins dir + id + json", () => {
    expect(stateFilePath("/tmp/s", "abc")).toBe("/tmp/s/abc.json");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/pi-tamagotchai && npx vitest run`
Expected: FAIL — `src/state.ts` not found / cannot resolve module

- [ ] **Step 3: Write minimal implementation**

```json
// plugins/pi-tamagotchai/package.json
{
  "name": "pi-tamagotchai",
  "version": "0.1.0",
  "description": "pi extension: writes session status JSON for the tamagotchai display daemon",
  "main": "./src/index.ts",
  "pi": {
    "extensions": ["./src/index.ts"]
  },
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "vitest": "^2.0.0",
    "typescript": "^5.5.0",
    "@types/node": "^20.0.0"
  }
}
```

```json
// plugins/pi-tamagotchai/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["src", "test"]
}
```

```typescript
// plugins/pi-tamagotchai/src/state.ts
import { writeFileSync, renameSync, unlinkSync, existsSync } from "node:fs";
import { join } from "node:path";

export interface AgentState {
  status: string;
  message: string;
  last_heartbeat: string;
  pending: number;
  metadata: {
    project?: string;
    model?: string;
    tool_name?: string;
    turn_count?: number;
    tools_executed?: number;
    tokens_input?: number;
    tokens_output?: number;
    tokens_total?: number;
    cost_usd?: number;
    session_duration_ms?: number;
    source: "pi";
  };
}

function nowIso(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function defaultState(project: string): AgentState {
  return {
    status: "working",
    message: "session started",
    last_heartbeat: nowIso(),
    pending: 1,
    metadata: { project, source: "pi", turn_count: 0, tools_executed: 0, tokens_input: 0, tokens_output: 0, tokens_total: 0, cost_usd: 0 },
  };
}

export function extractUsage(message: any): { tokens_input: number; tokens_output: number; tokens_total: number; cost_usd: number } | null {
  const u = message?.usage;
  if (!u) return null;
  return {
    tokens_input: Number(u.input ?? 0),
    tokens_output: Number(u.output ?? 0),
    tokens_total: Number(u.totalTokens ?? 0),
    cost_usd: Number(u?.cost?.total ?? 0),
  };
}

export function applyEvent(state: AgentState, event: { type: string; [k: string]: any }, ctx: { cwd?: string; model?: { provider?: string; id?: string } }): AgentState {
  const next: AgentState = { ...state, metadata: { ...state.metadata } };
  switch (event.type) {
    case "session_start":
      next.status = "working";
      next.message = "session started";
      next.metadata.project = ctx?.cwd?.split("/").pop() || state.metadata.project;
      break;
    case "before_agent_start":
      next.status = "working";
      next.message = String(event.prompt ?? "").slice(0, 60);
      break;
    case "tool_execution_start":
      next.status = "working";
      next.message = `tool: ${event.toolName}`;
      next.metadata.tool_name = event.toolName;
      break;
    case "tool_execution_end": {
      next.metadata.tools_executed = (state.metadata.tools_executed ?? 0) + 1;
      next.status = event.isError ? "error" : "working";
      next.message = `tool: ${event.toolName}`;
      break;
    }
    case "turn_start":
      next.metadata.turn_count = (state.metadata.turn_count ?? 0) + 1;
      break;
    case "turn_end":
      break;
    case "message_end": {
      const u = extractUsage(event.message);
      if (u) {
        next.metadata.tokens_input = (state.metadata.tokens_input ?? 0) + u.tokens_input;
        next.metadata.tokens_output = (state.metadata.tokens_output ?? 0) + u.tokens_output;
        next.metadata.tokens_total = (state.metadata.tokens_total ?? 0) + u.tokens_total;
        next.metadata.cost_usd = Number(((state.metadata.cost_usd ?? 0) + u.cost_usd).toFixed(4));
      }
      if (ctx?.model) next.metadata.model = `${ctx.model.provider ?? ""}/${ctx.model.id ?? ""}`.replace(/^\//, "");
      break;
    }
    case "agent_settled":
      next.status = "idle";
      next.message = "settled";
      next.pending = 0;
      break;
    default:
      return state;
  }
  next.last_heartbeat = nowIso();
  return next;
}

export function stateFilePath(sessionsDir: string, sessionId: string): string {
  return join(sessionsDir, `${sessionId}.json`);
}

export function atomicWrite(path: string, state: AgentState): void {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(state));
  renameSync(tmp, path);
}

export function deleteState(path: string): void {
  try { unlinkSync(path); } catch (e: any) { if (e.code !== "ENOENT") throw e; }
}

export function heartbeat(state: AgentState): AgentState {
  return { ...state, last_heartbeat: nowIso() };
}

export { existsSync };
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/pi-tamagotchai && npm install && npx vitest run`
Expected: PASS (all state.test.ts tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/pi-tamagotchai/package.json plugins/pi-tamagotchai/tsconfig.json plugins/pi-tamagotchai/src/state.ts plugins/pi-tamagotchai/test/state.test.ts plugins/pi-tamagotchai/README.md
git commit -m "feat(pi-tamagotchai): pure state functions + tests"
```

`plugins/pi-tamagotchai/README.md` content:

```markdown
# pi-tamagotchai

pi extension that writes live session status to JSON files for the
tamagotchai-agentd daemon (file backend). No sockets; files only.

State dir: `~/.pi/agent/tamagotchai/sessions/<session-id>.json`

Install (global): `ln -s /home/senpai/tamagotchai/plugins/pi-tamagotchai ~/.pi/agent/extensions/pi-tamagotchai`

Reload in pi: `/reload`
```

---

## Task 7: pi extension factory (event wiring to files)

**Files:**
- Create: `plugins/pi-tamagotchai/src/index.ts`

**Interfaces:**
- Consumes: `applyEvent`, `defaultState`, `stateFilePath`, `atomicWrite`, `deleteState` from `state.ts` (Task 6); pi `ExtensionAPI` (`pi.on(event, handler)`)
- Produces: default-exported factory `function (pi: ExtensionAPI)` that:
  - On `session_start`: derive session id from `ctx.sessionManager.getSessionId()`, project from `ctx.cwd`, build `defaultState`, atomic-write the file. Keep the path in a per-session `Map` keyed by session id (handles reload).
  - On `before_agent_start`, `tool_execution_start`, `tool_execution_end`, `turn_start`, `turn_end`, `message_end`, `agent_settled`: load current state from the file (re-read, since we don't keep in-process state across async boundaries reliably), `applyEvent`, atomic-write. If no file exists (race), skip.
  - On `session_shutdown`: `deleteState` the file for this session id, remove from the `Map`.

- [ ] **Step 1: Write the failing test**

The factory is thin glue to the pi runtime, hard to unit-test in isolation. Test the wiring logic via a mock `pi` object that records handlers and replays events:

```typescript
// plugins/pi-tamagotchai/test/index.test.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

describe("factory wiring", () => {
  let dir: string;
  let handlers: Record<string, (e: any, ctx: any) => void>;
  let ctx: any;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "tamagotchai-"));
    handlers = {};
    const pi: any = {
      on: (name: string, fn: (e: any, ctx: any) => void) => { handlers[name] = fn; },
    };
    ctx = {
      cwd: "/home/senpai/tamagotchai",
      sessionManager: { getSessionId: () => "sess-1" },
      model: { provider: "anthropic", id: "claude-3.7-sonnet" },
    };
    // load the factory (uses relative paths to src)
    const factory = (await import("../src/index")).default;
    factory(pi);
    // point the extension at our temp dir by overriding process env
    process.env.TAMAGOTCHAI_SESSIONS_DIR = dir;
  });

  it("session_start writes a file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    const files = readdirSync(dir);
    expect(files).toContain("sess-1.json");
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.status).toBe("working");
    expect(st.metadata.source).toBe("pi");
  });

  it("tool_execution_start then end update the file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["tool_execution_start"]({ type: "tool_execution_start", toolCallId: "t1", toolName: "bash", args: {} }, ctx);
    handlers["tool_execution_end"]({ type: "tool_execution_end", toolCallId: "t1", toolName: "bash", result: "", isError: false }, ctx);
    const st = JSON.parse(readFileSync(join(dir, "sess-1.json"), "utf8"));
    expect(st.metadata.tools_executed).toBe(1);
    expect(st.message).toBe("tool: bash");
  });

  it("session_shutdown deletes the file", () => {
    handlers["session_start"]({ reason: "startup" }, ctx);
    handlers["session_shutdown"]({ reason: "quit" }, ctx);
    expect(readdirSync(dir)).not.toContain("sess-1.json");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd plugins/pi-tamagotchai && npx vitest run`
Expected: FAIL — `src/index.ts` not found

- [ ] **Step 3: Write minimal implementation**

```typescript
// plugins/pi-tamagotchai/src/index.ts
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { AgentState, applyEvent, atomicWrite, defaultState, deleteState, stateFilePath } from "./state";

function sessionsDir(): string {
  return process.env.TAMAGOTCHAI_SESSIONS_DIR || join(homedir(), ".pi", "agent", "tamagotchai", "sessions");
}

function loadState(path: string): AgentState | null {
  try { return JSON.parse(readFileSync(path, "utf8")) as AgentState; } catch { return null; }
}

export default function (pi: ExtensionAPI): void {
  const paths = new Map<string, string>();

  function pathFor(sessionId: string): string {
    let p = paths.get(sessionId);
    if (!p) { p = stateFilePath(sessionsDir(), sessionId); paths.set(sessionId, p); }
    return p;
  }

  function withState(event: any, ctx: any): void {
    const sid = ctx?.sessionManager?.getSessionId?.();
    if (!sid) return;
    const path = pathFor(sid);
    const prev = loadState(path);
    if (!prev) return; // race: no session_start seen yet
    const next = applyEvent(prev, event, ctx);
    atomicWrite(path, next);
  }

  pi.on("session_start", (event: any, ctx: any) => {
    const sid = ctx?.sessionManager?.getSessionId?.();
    if (!sid) return;
    const path = pathFor(sid);
    const project = ctx?.cwd?.split("/").pop() || "unknown";
    atomicWrite(path, defaultState(project));
  });

  pi.on("before_agent_start", (event: any, ctx: any) => withState({ ...event, type: "before_agent_start" }, ctx));
  pi.on("tool_execution_start", (event: any, ctx: any) => withState(event, ctx));
  pi.on("tool_execution_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("turn_start", (event: any, ctx: any) => withState(event, ctx));
  pi.on("turn_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("message_end", (event: any, ctx: any) => withState(event, ctx));
  pi.on("agent_settled", (event: any, ctx: any) => withState({ type: "agent_settled" }, ctx));

  pi.on("session_shutdown", (event: any, ctx: any) => {
    const sid = ctx?.sessionManager?.getSessionId?.();
    if (!sid) return;
    deleteState(pathFor(sid));
    paths.delete(sid);
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd plugins/pi-tamagotchai && npx vitest run`
Expected: PASS (factory + state tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/pi-tamagotchai/src/index.ts plugins/pi-tamagotchai/test/index.test.ts
git commit -m "feat(pi-tamagotchai): factory wiring events to state files"
```

---

## Task 8: Display agent_feed array expansion (backward compatible)

**Files:**
- Modify: `core/screens/agent_feed.py`
- Test: `tests/test_agent_feed_array.py`

**Goal:** `agent_feed` currently expects a dict per agent URL (`core/screens/agent_feed.py:28-30`). Make it also accept an array and expand into multiple rows. Dict responses still render as one row (no behavior change for existing single-session endpoints).

**Interfaces:**
- Consumes: existing `Screen` base, `aiohttp`
- Produces: `_fetch_agent` returns `list[dict]` (always, even for one); `fetch()` flattens. Each row gets `name` from config (the agent's config name). Multi-row names stay identical (the `message`/metadata differentiates).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_feed_array.py
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.screens.agent_feed import AgentFeedScreen, _fetch_agent


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_session(payload):
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=payload)
    session = AsyncMock()
    session.get = AsyncMock(return_value=resp)
    return session


def test_fetch_agent_dict_returns_one_row():
    session = _make_session({"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}})
    rows = _run(_fetch_agent(session, "pi", "http://x/status"))
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["name"] == "pi"
    assert rows[0]["status"] == "working"


def test_fetch_agent_array_returns_multiple_rows():
    payload = [
        {"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}},
        {"status": "idle", "last_heartbeat": "2026-08-16T09:00:00Z", "metadata": {}},
    ]
    session = _make_session(payload)
    rows = _run(_fetch_agent(session, "pi", "http://x/status/all"))
    assert len(rows) == 2
    assert all(r["name"] == "pi" for r in rows)


def test_fetch_agent_error_returns_error_row():
    session = AsyncMock()
    session.get = AsyncMock(side_effect=Exception("boom"))
    rows = _run(_fetch_agent(session, "pi", "http://x/status"))
    assert len(rows) == 1
    assert rows[0].get("__fetch_error") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agent_feed_array.py -v`
Expected: FAIL — `_fetch_agent` returns a dict, not a list (existing code returns `data` dict)

- [ ] **Step 3: Write minimal implementation**

Modify `core/screens/agent_feed.py`:

Replace `_fetch_agent`:

```python
async def _fetch_agent(session: Any, name: str, url: str) -> List[Dict[str, Any]]:
    import aiohttp
    try:
        resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
        resp.raise_for_status()
        data = await resp.json()
        if isinstance(data, list):
            rows = [d if isinstance(d, dict) else {"value": d} for d in data]
        elif isinstance(data, dict):
            rows = [data]
        else:
            rows = [{"value": data}]
        for r in rows:
            r.setdefault("name", name)
        return rows
    except Exception as e:
        logger.warning(f"Fetch failed for agent {name}: {e}")
        return [{"name": name, "__fetch_error": True}]
```

Replace the `fetch` loop to flatten (the `tasks`/`results`/`processed` block):

```python
        tasks = [_fetch_agent(session, a.name, a.url) for a in self._config.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        stale_threshold = self._config.stale_threshold
        processed: List[Dict[str, Any]] = []

        for result in results:
            if isinstance(result, Exception):
                processed.append({"name": "?", "status": "error", "__fetch_error": True})
                continue
            for data in result:  # result is now a list[dict]
                heartbeat = data.get("last_heartbeat")
                if heartbeat and not data.get("__fetch_error"):
                    try:
                        dt = datetime.fromisoformat(heartbeat)
                        age = (datetime.now(timezone.utc) - dt).total_seconds()
                        if age > stale_threshold:
                            data["status"] = "offline"
                    except (ValueError, TypeError):
                        pass
                processed.append(data)

        self._agents_data = processed
```

Leave `render`, `has_changed`, `_data_hash` unchanged (they already iterate `self._agents_data`).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agent_feed_array.py -v`
Expected: PASS (3 tests)

Then run the full existing suite to confirm no regressions:
Run: `python -m pytest tests/ -v`
Expected: PASS (all existing tests still pass)

- [ ] **Step 5: Commit**

```bash
git add core/screens/agent_feed.py tests/test_agent_feed_array.py
git commit -m "feat(agent_feed): expand array responses into multiple rows (backward compat)"
```

---

## Task 9: Display config (screens.yml + example)

**Files:**
- Modify: `config/screens.yml.example`
- Modify: `config/screens.yml` (live, gitignored)

**Goal:** Replace the dead `opencode` screen with an `agent_feed` pulling from real hosts (pi local, hermes1/hermes2 tunnels). Drop the dead OpenCode category from the AI Services board. Keep Device screen.

- [ ] **Step 1: Read current files**

Read `config/screens.yml.example` and `config/screens.yml` to see the existing three screens and their dead URLs (documented in the spec problem statement: opencode → `192.168.1.117:7788`, AI Services → `127.0.0.1:7788`).

- [ ] **Step 2: Replace the example**

Overwrite `config/screens.yml.example` with:

```yaml
# tamagotchai screens configuration
# One daemon per agent host serves Standard Agent Status JSON on :7788.
# pi runs on this Pi Zero (127.0.0.1); hermes agents are remote (tunnel URLs).
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
        url: https://hermes1.<your-cf-tunnel>.example/status/all
      - name: hermes2
        url: https://hermes2.<your-cf-tunnel>.example/status/all

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

- [ ] **Step 3: Apply same to live config**

Copy the example to `config/screens.yml` (it is gitignored). The user fills in the real `<your-cf-tunnel>` hostnames during setup.

- [ ] **Step 4: Verify config loads**

Run: `python app.py preview`
Expected: renders the `Agents` screen (with connection-error rows since no daemon/tunnels are up yet), `AI Services`, and `Device` — no crash, no "setup hint" forever screen.

Run: `python app.py doctor`
Expected: shows SPI/GPIO missing (fine on dev), config loads cleanly.

- [ ] **Step 5: Commit**

```bash
git add config/screens.yml.example
git commit -m "config: replace dead opencode screen with agent_feed (pi + hermes)"
```

---

## Task 10: Install scripts + live integration checklist

**Files:**
- Create: `plugins/tamagotchai-agentd/install.sh`
- Create: `plugins/pi-tamagotchai/install.sh`

**Goal:** One-command install for the daemon (systemd) and the extension (symlink + reload).

- [ ] **Step 1: Write the install scripts**

```bash
# plugins/tamagotchai-agentd/install.sh
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SVC="/etc/systemd/system/tamagotchai-agentd@.service"
sudo cp "$HERE/agentd.service" "$SVC"
sudo systemctl daemon-reload
echo "Installed $SVC"
echo "Enable for a user: sudo systemctl enable --now tamagotchai-agentd@<user>"
```

```bash
# plugins/pi-tamagotchai/install.sh
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.pi/agent/extensions/pi-tamagotchai"
mkdir -p "$HOME/.pi/agent/extensions"
ln -sfn "$HERE" "$DEST"
mkdir -p "$HOME/.pi/agent/tamagotchai/sessions"
echo "Symlinked $HERE -> $DEST"
echo "Run /reload in pi to activate."
```

- [ ] **Step 2: Make executable and commit**

```bash
chmod +x plugins/tamagotchai-agentd/install.sh plugins/pi-tamagotchai/install.sh
git add plugins/tamagotchai-agentd/install.sh plugins/pi-tamagotchai/install.sh
git commit -m "chore: install scripts for daemon + extension"
```

- [ ] **Step 3: Live integration checklist (run on the Pi Zero)**

Document in `plugins/tamagotchai-agentd/README.md` under "Live test":

```markdown
## Live integration test (Pi Zero)

1. `./plugins/pi-tamagotchai/install.sh` then `/reload` in pi.
2. `./plugins/tamagotchai-agentd/install.sh && sudo systemctl enable --now tamagotchai-agentd@senpai`
3. `curl http://127.0.0.1:7788/status/all` → array with one pi session (working).
4. `python app.py once` → e-paper shows the pi row in `Agents`.
5. Trigger a pi action in this very session → `curl .../status/all` shows `working` + `tool: ...`.
6. Stop pi (`/quit`) → row stays for `stale_threshold` then goes `offline` after 120s.
7. Hermes: on each hermes host, install the daemon with `TAMAGOTCHAI_BACKEND=webhook`,
   set `HERMES_WEBHOOK_SECRET`, point hermes `hooks.outbound` at `http://127.0.0.1:7788/ingest`,
   expose `https://hermesN.<tunnel>/status/all` via cloudflared.
8. Fill real tunnel hostnames into `config/screens.yml`, `python app.py once` → all three rows live.
```

- [ ] **Step 4: Final full test run**

Run: `python -m pytest tests/ -v && (cd plugins/pi-tamagotchai && npx vitest run)`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add plugins/tamagotchai-agentd/README.md
git commit -m "docs: live integration checklist"
```

---

## Self-Review

### Spec coverage
- pi extension writes session state files (no sockets) — Task 6, 7 ✓
- Always-on daemon, file backend (pi) + webhook backend (hermes), `/health` `/status` `/status/all` `/ingest` — Tasks 1–5 ✓
- Daemon owns staleness (agents never self-idle) — Task 1 `sweep`, Task 5 sweep loop ✓
- Display GET-only, `screens.yml` real URLs, opencode dropped — Task 9 ✓
- Standard Agent Status JSON + pi-native metadata (model, tokens, cost, tool_name, turn_count, tools_executed) — Task 6 `state.ts` ✓
- HMAC-SHA256 verify on `/ingest` — Task 4 ✓
- Transport-agnostic (`0.0.0.0:7788`, tunnels are ops) — Task 5 + README ✓
- Spec delta: agent_feed array expansion (backward compat) — Task 8 ✓

### Placeholder scan
No "TBD"/"implement later"/"add error handling" steps. Hermes event names are flagged for verification at implementation (Global Constraints), with the minimal mapping table given in Task 4. All code blocks contain actual code.

### Type consistency
- `SessionRegistry.update/remove/sweep/snapshot_all/latest` — used identically in Tasks 1, 3, 4, 5.
- `make_handler(registry, webhook_backend=None)` — Task 2 defines, Task 5 calls with `webhook_backend=webhook_backend`.
- `FileWatchBackend(registry, sessions_dir)` + `.poll()` — Task 3 defines, Task 5 uses.
- `WebhookBackend(registry, secret)` + `.handle(body, headers)` + `.map_event(name, payload)` — Task 4 defines, Task 2 server delegates `handle`, Task 5 instantiates.
- `applyEvent/defaultState/atomicWrite/deleteState/stateFilePath` — Task 6 defines, Task 7 uses.
- `_fetch_agent` returns `list[dict]` — Task 8 defines, `fetch()` flattens. Existing `render`/`_data_hash` iterate `self._agents_data` unchanged.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-16-pi-hermes-agent-feed.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
