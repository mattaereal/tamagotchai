"""Provider adapters."""

import logging
from typing import Dict, Any

from ai_health_board.config import ProviderConfig

logger = logging.getLogger(__name__)

_BACKENDS: Dict[str, Any] = {
    "statuspage": "ai_health_board.providers.statuspage.StatuspageProvider",
}


def get_provider(config: ProviderConfig) -> Any:
    """Get a provider instance from a ProviderConfig.

    Args:
        config: ProviderConfig with name, type, url, and components

    Returns:
        Instantiated provider with config applied
    """
    provider_type = config.type
    if provider_type not in _BACKENDS:
        available = ", ".join(_BACKENDS.keys())
        raise ValueError(
            f"Unknown provider type '{provider_type}'. Available: {available}"
        )
    module_name, class_name = _BACKENDS[provider_type].rsplit(".", 1)
    module = __import__(module_name, fromlist=[class_name])
    cls = getattr(module, class_name)
    logger.debug(f"Using provider: {provider_type} ({config.name})")

    # Instantiate with config parameters
    return cls(
        display_name=config.name,
        url=config.url,
        component_keys=config.components,
    )
