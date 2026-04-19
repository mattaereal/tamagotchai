"""Display backends."""

import logging
from typing import Dict, Any, Union

from ai_health_board.config import DisplayConfig

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, str] = {
    "mock": "ai_health_board.display.mock_png.MockPNGDisplay",
    "waveshare_2in13_v1": "ai_health_board.display.waveshare_2in13_v1.Waveshare2in13V1Display",
    "waveshare_2in13_v2": "ai_health_board.display.waveshare_2in13_v2.Waveshare2in13V2Display",
    "waveshare_2in13_v3": "ai_health_board.display.waveshare_2in13_v3.Waveshare2in13V3Display",
    "waveshare_2in13_v4": "ai_health_board.display.waveshare_2in13_v4.Waveshare2in13V4Display",
    "waveshare_2in13bc": "ai_health_board.display.waveshare_2in13bc.Waveshare2in13BCDisplay",
    "waveshare_2in13b_v3": "ai_health_board.display.waveshare_2in13b_v3.Waveshare2in13BV3Display",
    "waveshare_2in13b_v4": "ai_health_board.display.waveshare_2in13b_v4.Waveshare2in13BV4Display",
    "waveshare_2in13d": "ai_health_board.display.waveshare_2in13d.Waveshare2in13DDisplay",
    "waveshare_2in13g": "ai_health_board.display.waveshare_2in13g.Waveshare2in13GDisplay",
}


def get_display(config: Union[DisplayConfig, Dict[str, Any]]) -> Any:
    """Get a display backend by name from config."""
    if isinstance(config, DisplayConfig):
        backend_name = config.backend
    else:
        backend_name = config.get("backend", "mock")

    if backend_name not in _BACKENDS:
        available = ", ".join(sorted(_BACKENDS.keys()))
        raise ValueError(
            f"Unknown display backend '{backend_name}'. Available: {available}"
        )

    module_name, class_name = _BACKENDS[backend_name].rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    cls = getattr(module, class_name)
    logger.info(f"Using display backend: {backend_name}")
    return cls(config)


def backend_names() -> list[str]:
    return sorted(_BACKENDS.keys())
