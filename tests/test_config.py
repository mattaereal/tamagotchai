"""Tests for config loading."""
import pytest
import tempfile
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_health_board.config import load_config, AppConfig, DisplayConfig, ProviderConfig

def test_load_valid_config():
    """Test loading a valid configuration."""
    yaml_content = """
refresh_seconds: 60
timezone: UTC
display:
  backend: mock
  width: 250
  height: 122
  rotation: 90
  full_refresh_every_n_updates: 3
providers:
  - name: TestService
    type: statuspage
    url: https://example.com/api/summary.json
    components:
      - comp1
      - comp2
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        fname = f.name

    try:
        cfg = load_config(fname)
        assert isinstance(cfg, AppConfig)
        assert cfg.refresh_seconds == 60
        assert cfg.timezone == "UTC"
        assert isinstance(cfg.display, DisplayConfig)
        assert cfg.display.backend == "mock"
        assert cfg.display.width == 250
        assert cfg.display.height == 122
        assert cfg.display.rotation == 90
        assert cfg.display.full_refresh_every_n_updates == 3
        assert len(cfg.providers) == 1
        p = cfg.providers[0]
        assert p.name == "TestService"
        assert p.type == "statuspage"
        assert p.url == "https://example.com/api/summary.json"
        assert p.components == ["comp1", "comp2"]
    finally:
        os.unlink(fname)

def test_load_config_defaults():
    """Test loading config with minimal/default values."""
    yaml_content = """
refresh_seconds: 60
timezone: UTC
display:
  backend: mock
  width: 250
  height: 122
  rotation: 90
providers:
  - name: Minimal
    type: statuspage
    url: https://example.com/api/summary.json
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        fname = f.name

    try:
        cfg = load_config(fname)
        assert cfg.refresh_seconds == 60  # default from yaml
        assert cfg.timezone == "UTC"  # default
        assert cfg.display.backend == "mock"  # default
        assert cfg.display.width == 250
        assert cfg.display.height == 122
        assert cfg.display.rotation == 90
        assert cfg.display.full_refresh_every_n_updates == 6  # default from DisplayConfig
        assert len(cfg.providers) == 1
    finally:
        os.unlink(fname)

def test_load_config_invalid_refresh():
    """Test that invalid refresh_seconds raises ValueError."""
    yaml_content = """
refresh_seconds: -1
providers:
  - name: A
    type: statuspage
    url: https://example.com/api/summary.json
    components: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        fname = f.name

    try:
        with pytest.raises(ValueError, match="refresh_seconds must be positive"):
            load_config(fname)
    finally:
        os.unlink(fname)

def test_load_config_no_providers(caplog):
    """Test loading config with no providers (should log warning)."""
    yaml_content = """
refresh_seconds: 300
providers: []
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        fname = f.name

    try:
        with caplog.at_level(logging.WARNING):
            cfg = load_config(fname)
        assert len(cfg.providers) == 0
        assert "No providers configured" in caplog.text
    finally:
        os.unlink(fname)
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
