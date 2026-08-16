"""Tests for agent_feed array expansion (backward compatible).

A daemon /status/all endpoint returns a JSON array of sessions; a legacy
/status endpoint returns a single dict. Both must render rows.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from core.screens.agent_feed import AgentFeedScreen, _fetch_agent


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_session(payload):
    resp = AsyncMock()
    resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=payload)
    session = AsyncMock()
    session.get = AsyncMock(return_value=resp)
    return session


def test_fetch_agent_dict_returns_one_row():
    session = _make_session(
        {"status": "working", "last_heartbeat": "2026-08-16T10:00:00Z", "metadata": {}}
    )
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
