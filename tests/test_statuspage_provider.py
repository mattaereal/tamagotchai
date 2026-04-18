"""Tests for Statuspage provider normalization."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_health_board.providers.statuspage import StatuspageProvider
from ai_health_board.models import ServiceStatus


def test_normalize_operational():
    """Test normalization of 'operational' status."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "none"},
        "components": [
            {"name": "API", "status": "operational"},
        ],
    }
    result = provider.normalize(raw)
    assert "API" in result
    assert result["API"] == ServiceStatus.OK


def test_normalize_degraded_performance():
    """Test normalization of 'degraded_performance'."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "minor"},
        "components": [
            {"name": "API", "status": "degraded_performance"},
        ],
    }
    result = provider.normalize(raw)
    assert result["API"] == ServiceStatus.DEGRADED


def test_normalize_partial_outage():
    """Test normalization of 'partial_outage'."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "major"},
        "components": [
            {"name": "API", "status": "partial_outage"},
        ],
    }
    result = provider.normalize(raw)
    assert result["API"] == ServiceStatus.DEGRADED


def test_normalize_major_outage():
    """Test normalization of 'major_outage'."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "critical"},
        "components": [
            {"name": "API", "status": "major_outage"},
        ],
    }
    result = provider.normalize(raw)
    assert result["API"] == ServiceStatus.DOWN


def test_normalize_unknown_status():
    """Test normalization of unknown status falls back to UNKNOWN."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "none"},
        "components": [
            {"name": "API", "status": "blowing_up"},
        ],
    }
    result = provider.normalize(raw)
    assert result["API"] == ServiceStatus.UNKNOWN


def test_normalize_top_level_dict():
    """Test normalization when components are at top-level dict values."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    raw = {
        "status": {"indicator": "none"},
        "components": {
            "API": {"status": "operational"},
            "DB": {"status": "major_outage"},
        },
    }
    result = provider.normalize(raw)
    assert result["API"] == ServiceStatus.OK
    assert result["DB"] == ServiceStatus.DOWN


def test_normalize_empty():
    """Test normalization of empty raw data."""
    provider = StatuspageProvider(display_name="Test", url="", component_keys=[])
    result = provider.normalize({})
    assert len(result) == 0


def test_display_name():
    provider = StatuspageProvider(display_name="My Service", url="", component_keys=[])
    assert provider.display_name() == "My Service"


def test_provider_type():
    provider = StatuspageProvider(display_name="My", url="", component_keys=[])
    assert provider.provider_type() == "statuspage"
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
