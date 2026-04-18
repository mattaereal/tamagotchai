"""Data models for AI health board."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ServiceStatus(str, Enum):
    """Normalized service status."""
    OK = "OK"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"

    def icon(self) -> str:
        mapping = {
            self.OK: "[OK]",
            self.DEGRADED: "[!]",
            self.DOWN: "[X]",
            self.UNKNOWN: "[?]",
        }
        return mapping.get(self, "[?]")


@dataclass
class ComponentStatus:
    """Status of a single component."""
    name: str
    status: ServiceStatus
    upstream_status: Optional[Any] = None
    upstream_output: Optional[Any] = None
    failure_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "upstream_status": self.upstream_status,
            "failure_count": self.failure_count,
        }


@dataclass
class ProviderStatus:
    """Status of a provider and all of its components."""
    name: str
    provider_type: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    components: List[ComponentStatus] = field(default_factory=list)
    last_successful_refresh: Optional[datetime] = None
    consecutive_failures: int = 0
    raw_upstream: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider_type": self.provider_type,
            "status": self.status.value,
            "components": [c.to_dict() for c in self.components],
            "last_successful_refresh": (
                self.last_successful_refresh.isoformat()
                if self.last_successful_refresh
                else None
            ),
            "consecutive_failures": self.consecutive_failures,
        }


@dataclass
class AppState:
    """Application state cache."""
    last_refresh: Optional[datetime] = None
    providers: List[ProviderStatus] = field(default_factory=list)
    stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_refresh": (
                self.last_refresh.isoformat() if self.last_refresh else None
            ),
            "stale": self.stale,
            "providers": [p.to_dict() for p in self.providers],
        }
