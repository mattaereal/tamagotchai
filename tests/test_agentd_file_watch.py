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