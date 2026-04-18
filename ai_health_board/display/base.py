"""Display abstraction layer."""

from __future__ import annotations

import abc
from typing import Any, Dict

from PIL import Image


class DisplayBackend(abc.ABC):
    """Abstract display backend."""

    @abc.abstractmethod
    def render(self, state: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def render_image(self, img: Image.Image) -> None:
        """Render a PIL Image directly to the display.

        The backend decides internally whether to use full or partial refresh.

        Args:
            img: PIL Image in mode '1', sized to match display dimensions.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def flush(self) -> None:
        """Push rendered content to hardware (noop for mock)."""
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """Shut down the display hardware cleanly."""
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
