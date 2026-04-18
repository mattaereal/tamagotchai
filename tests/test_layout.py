"""Tests for layout rendering."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_health_board.render.layout import render_components
from ai_health_board.models import ProviderStatus, ComponentStatus, ServiceStatus


def test_render_empty():
    """Test rendering with empty state."""
    state = {
        "last_refresh": None,
        "stale": False,
        "providers": [],
    }
    display_cfg = {"width": 250, "height": 122}
    # Should not crash
    render_components(state, display_cfg)


def test_render_with_providers():
    """Test rendering with actual provider data."""
    providers = [
        ProviderStatus(
            name="Claude",
            provider_type="statuspage",
            status=ServiceStatus.OK,
            components=[
                ComponentStatus("claude.ai", ServiceStatus.OK),
                ComponentStatus("API", ServiceStatus.DEGRADED),
            ],
        ),
        ProviderStatus(
            name="OpenAI",
            provider_type="statuspage",
            status=ServiceStatus.DOWN,
            components=[
                ComponentStatus("ChatGPT", ServiceStatus.DOWN),
                ComponentStatus("API", ServiceStatus.OK),
            ],
        ),
    ]
    state = {
        "last_refresh": "2024-01-15T12:00:00",
        "stale": False,
        "providers": [p.to_dict() for p in providers],
    }
    display_cfg = {"width": 250, "height": 122}
    # Should not crash
    render_components(state, display_cfg)
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
