"""Display abstraction layer."""
from __future__ import annotations

import abc
from typing import Any, Dict

from PIL import Image, ImageDraw, ImageFont

from ..models import ComponentStatus, ProviderStatus


class DisplayBackend(abc.ABC):
    """Abstract display backend."""

    @abc.abstractmethod
    def render(self, state: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def flush(self) -> None:
        """Push rendered content to hardware (noop for mock)."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def size(self) -> tuple[int, int]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def width(self) -> int:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def height(self) -> int:
        raise NotImplementedError
