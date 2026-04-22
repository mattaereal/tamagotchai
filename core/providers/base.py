"""Base provider interface and status normalization."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.models import ComponentStatus, ProviderStatus, ServiceStatus

logger = logging.getLogger(__name__)


class StatusProvider(ABC):
    """Abstract interface for status providers."""

    @abstractmethod
    def provider_type(self) -> str:
        """Return a short machine-readable type string."""
        raise NotImplementedError

    @abstractmethod
    def display_name(self) -> str:
        """Return a human-readable display name."""
        raise NotImplementedError

    async def fetch_status(self, session: Any, timeout: int = 10) -> Dict[str, Any]:
        """Fetch raw status from the upstream service.

        Args:
            session: aiohttp ClientSession for making HTTP requests.
            timeout: Request timeout in seconds.

        Returns:
            Raw upstream JSON-compatible dict.
        """
        raise NotImplementedError

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, ComponentStatus]:
        """Convert raw upstream data into normalized ComponentStatus mapping.

        Subclasses must override this.
        """
        return {}

    async def get_status(
        self, session: Any, timeout: int = 10
    ) -> ProviderStatus:
        """Perform a fetch+normalize cycle and return ProviderStatus."""
        provider = ProviderStatus(
            name=self.display_name(),
            provider_type=self.provider_type(),
            components=[],
        )

        try:
            raw = await self.fetch_status(session, timeout=timeout)
            provider.raw_upstream = raw
            normalized = self.normalize(raw)

            if not normalized and self._has_components_in_raw(raw):
                normalized = self._normalize_from_raw_values(raw)

            for name, status in normalized.items():
                provider.components.append(
                    ComponentStatus(name=name, status=status)
                )

            provider.status = self._aggregate_status(provider.components)
            provider.consecutive_failures = 0
            provider.last_successful_refresh = None  # set by caller
            logger.debug(
                f"Provider {self.display_name()} status: "
                f"{provider.status.value}"
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                f"Failed to fetch status for {self.display_name()}: {e}",
                exc_info=True,
            )
            provider.consecutive_failures += 1
            provider.status = ServiceStatus.DOWN

        return provider

    def _has_components_in_raw(self, raw: Dict[str, Any]) -> bool:
        """Heuristic check whether raw data contains component-like structure."""
        return any(isinstance(v, dict) for v in raw.values())

    def _normalize_from_raw_values(
        self, raw: Dict[str, Any]
    ) -> Dict[str, ComponentStatus]:
        """Fallback normalization: treat dict values as component statuses."""
        result: Dict[str, ComponentStatus] = {}
        for key, value in raw.items():
            status = self._infer_status_from_value(value)
            result[key] = ComponentStatus(name=key, status=status, upstream_status=value)
        return result

    def _infer_status_from_value(self, value: Any) -> ServiceStatus:
        """Map upstream value to normalized ServiceStatus."""
        if isinstance(value, dict):
            status_val = (
                (value.get("status") or "").lower()
                if isinstance(value.get("status"), str)
                else ""
            )
        elif isinstance(value, str):
            status_val = value.lower()
        else:
            status_val = str(value).lower()

        if status_val in (
            "operational",
            "up",
            "ok",
            "none",
            "none.",
            "green",
        ):
            return ServiceStatus.OK
        if status_val in (
            "degraded_performance",
            "degraded",
            "degraded performance",
            "partial_outage",
            "partial",
            "minor",
        ):
            return ServiceStatus.DEGRADED
        if status_val in (
            "major_outage",
            "major",
            "critical",
            "outage",
            "down",
            "offline",
        ):
            return ServiceStatus.DOWN
        return ServiceStatus.UNKNOWN

    def _aggregate_status(self, components: List[ComponentStatus]) -> ServiceStatus:
        """Aggregate component statuses into a provider-level status."""
        if not components:
            return ServiceStatus.UNKNOWN

        statuses = {c.status for c in components}
        if ServiceStatus.DOWN in statuses:
            return ServiceStatus.DOWN
        if ServiceStatus.DEGRADED in statuses:
            return ServiceStatus.DEGRADED
        if all(s == ServiceStatus.OK for s in statuses):
            return ServiceStatus.OK
        return ServiceStatus.UNKNOWN
