"""Atlassian Statuspage adapter."""
import logging
from typing import Any, Dict

from .base import StatusProvider, ServiceStatus

logger = logging.getLogger(__name__)

# Common statuspage statuses we map from upstream
UPSTREAM_MAP = {
    "operational": ServiceStatus.OK,
    "under_maintenance": ServiceStatus.DEGRADED,
    "degraded_performance": ServiceStatus.DEGRADED,
    "partial_outage": ServiceStatus.DEGRADED,
    "major_outage": ServiceStatus.DOWN,
}


class StatuspageProvider(StatusProvider):
    """Provider for Atlassian Statuspage-compatible JSON endpoints."""

    def provider_type(self) -> str:
        return "statuspage"

    def display_name(self) -> str:
        return self._display_name

    def __init__(self, display_name: str, url: str, component_keys: list):
        self._display_name = display_name
        self.url = url
        self.component_keys = component_keys

    async def fetch_status(self, session: Any) -> Dict[str, Any]:
        import aiohttp
        resp = await session.get(self.url, timeout=10)
        resp.raise_for_status()
        return await resp.json()

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, ServiceStatus]:
        """Normalize Statuspage summary JSON into component statuses.

        Expected shape (v2):
        {
          "page": {"id": ..., "name": ...},
          "status": {"indicator": "none" | "minor" | "major" | "critical"},
          "components": [
            {"id": "...", "name": "...", "status": "operational", ...}
          ]
        }
        """
        result: Dict[str, ServiceStatus] = {}

        # Overall page status (used as fallback/aggregate)
        page_status_raw = ""
        page_status = raw.get("status")
        if isinstance(page_status, dict):
            indicator = (page_status.get("indicator") or "").lower()
            page_status_raw = indicator

        # Map known upstream indicator strings
        overall = self._infer_status_from_value(page_status_raw)

        # Components list
        components_raw = raw.get("components")
        if isinstance(components_raw, list):
            for comp in components_raw:
                if not isinstance(comp, dict):
                    continue
                name = comp.get("name", "")
                if not name:
                    continue
                comp_status_raw = (comp.get("status") or "").lower()
                status = self._infer_status_from_value(comp_status_raw)
                result[name] = status

        # If no components were parsed, try the top-level "components"
        # key which some statuspages use as a flat map.
        if not result:
            comps = raw.get("components")
            if isinstance(comps, dict):
                for key, val in comps.items():
                    if isinstance(val, dict):
                        st = (val.get("status") or "").lower()
                    else:
                        st = str(val).lower()
                    result[key] = self._infer_status_from_value(st)

        # If we still have no components but the overall status is known,
        # synthesize a single synthetic component so the UI shows something.
        if not result and overall != ServiceStatus.UNKNOWN:
            result["statuspage"] = overall

        # If user configured specific component keys, filter to those.
        if self.component_keys:
            filtered: Dict[str, ServiceStatus] = {}
            for key in self.component_keys:
                if key in result:
                    filtered[key] = result[key]
                else:
                    # Mark as UNKNOWN when explicitly configured but not found
                    filtered[key] = ServiceStatus.UNKNOWN
                    logger.warning(
                        f"Component '{key}' not found in {self.display_name()} status data"
                    )
            return filtered

        return result
