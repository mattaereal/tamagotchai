"""Agent feed screen (template: agent_feed).

Shows multiple AI agents in a compact list on one screen.
Each agent serves the standard Agent Status JSON schema over HTTP.
Fetches all agent URLs in parallel, applies stale detection,
and renders a compact row per agent.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from PIL import Image

from .base import Screen
from ..config import ScreenConfig

logger = logging.getLogger(__name__)


async def _fetch_agent(session: Any, name: str, url: str) -> Dict[str, Any]:
    import aiohttp

    try:
        resp = await session.get(url, timeout=aiohttp.ClientTimeout(total=10))
        resp.raise_for_status()
        data = await resp.json()
        if not isinstance(data, dict):
            data = {"value": data}
        data["name"] = name
        return data
    except Exception as e:
        logger.warning(f"Fetch failed for agent {name}: {e}")
        return {"name": name, "__fetch_error": True}


class AgentFeedScreen(Screen):
    def __init__(self, config: ScreenConfig):
        self._config = config
        self._poll_interval = config.poll_interval
        self._display_duration = config.display_duration
        self._agents_data: List[Dict[str, Any]] = []
        self._last_hash: Optional[str] = None

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    @property
    def display_duration(self) -> int:
        return self._display_duration

    async def fetch(self, session: Any) -> None:
        if not self._config.agents:
            return

        tasks = [_fetch_agent(session, a.name, a.url) for a in self._config.agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        stale_threshold = self._config.stale_threshold
        processed: List[Dict[str, Any]] = []

        for result in results:
            if isinstance(result, Exception):
                processed.append(
                    {"name": "?", "status": "error", "__fetch_error": True}
                )
                continue

            data = result
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

    def render(self, width: int, height: int) -> Image.Image:
        from ui.templates import render as tpl_render
        from ui.canvas import Canvas

        agents = []
        all_failed = True
        for a in self._agents_data:
            failed = bool(a.get("__fetch_error"))
            if not failed:
                all_failed = False
            agents.append(
                {
                    "name": a.get("name", "?"),
                    "status": a.get("status", ""),
                    "message": a.get("message", ""),
                    "fetch_error": failed,
                    "metadata": a.get("metadata") if isinstance(a.get("metadata"), dict) else {},
                }
            )

        data = {
            "name": self._config.name,
            "agents": agents,
            "num_agents": len(self._agents_data),
            "show_hint": all_failed and len(self._agents_data) > 0,
        }

        self._last_hash = self._data_hash()
        return tpl_render("agent_feed", data, canvas=Canvas(width, height))

    def has_changed(self) -> bool:
        if self._last_hash is None:
            return True
        return self._data_hash() != self._last_hash

    def _data_hash(self) -> str:
        raw = str(
            sorted(
                (
                    a.get("name", ""),
                    a.get("status", ""),
                    str(a.get("metadata")),
                )
                for a in self._agents_data
            )
        )
        return hashlib.md5(raw.encode()).hexdigest()
