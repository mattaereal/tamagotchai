"""Provider adapters."""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, Any] = {
    "statuspage": "ai_health_board.providers.statuspage.StatuspageProvider",
}


def get_provider(provider_type: str) -> Any:
    """Get a provider by type string."""
    if provider_type not in _BACKENDS:
        available = ", ".join(_BACKENDS.keys())
        raise ValueError(
            f"Unknown provider type '{provider_type}'. Available: {available}"
        )
    module_name, class_name = _BACKENDS[provider_type].rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    cls = getattr(module, class_name)
    logger.debug(f"Using provider: {provider_type}")
    return cls()
