"""tamagotchai-agentd: always-on status daemon for the e-paper display."""
from __future__ import annotations

import logging
import threading
import time
import sys
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

from tamagotchai_agentd.config import parse_args
from tamagotchai_agentd.state import SessionRegistry
from tamagotchai_agentd.server import make_handler
from tamagotchai_agentd.backends.file_watch import FileWatchBackend
from tamagotchai_agentd.backends.webhook import WebhookBackend

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("tamagotchai-agentd")


def main(argv: list[str] | None = None) -> None:
    cfg = parse_args(argv)
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