"""Display backends."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, Any] = {
    "mock": "ai_health_board.display.mock_png.MockPNGDisplay",
    "waveshare_2in13": "ai_health_board.display.waveshare_2in13.Waveshare2in13Display",
}


def get_display(config: Dict[str, Any]) -> Any:
    """Get a display backend by name from config."""
    backend_name = config.get("backend", "mock")
    if backend_name not in _BACKENDS:
        available = ", ".join(_BACKENDS.keys())
        raise ValueError(f"Unknown display backend '{backend_name}'. Available: {available}")

    module_name, class_name = _BACKENDS[backend_name].rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    cls = getattr(module, class_name)
    logger.info(f"Using display backend: {backend_name}")
    return cls(config)
