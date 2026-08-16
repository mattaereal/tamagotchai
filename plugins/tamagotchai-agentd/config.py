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


def parse_args(argv: list[str] | None = None) -> Config:
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