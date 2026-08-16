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
