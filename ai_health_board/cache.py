"""Simple file-based cache for last successful state."""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_FILE = "cache/status.json"


def _ensure_dir(path: str) -> None:
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)


def load_cache() -> Optional[Dict[str, Any]]:
    """Load cached state from disk. Returns None if not found/invalid."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to read cache: {e}")
        return None


def save_cache(data: Dict[str, Any]) -> None:
    """Atomically write cache to disk."""
    _ensure_dir(CACHE_FILE)
    tmp = CACHE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        # Ensure written before rename (atomic on POSIX)
        f.flush()
        os.fsync(f.fileno())
        os.replace(tmp, CACHE_FILE)
    except OSError as e:
        logger.warning(f"Failed to write cache: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
