"""Tests for config loading (3-file directory-based config)."""

import pytest
import tempfile
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_health_board.config import load_config, AppConfig, DisplayConfig


def test_load_valid_config():
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write(
                "backend: mock\n"
                "width: 122\n"
                "height: 250\n"
                "rotation: 0\n"
                "full_refresh_every_n_updates: 3\n"
            )
        with open(os.path.join(td, "tamagotchai.yml"), "w") as f:
            f.write("refresh_seconds: 60\ntimezone: UTC\n")
        with open(os.path.join(td, "screens.yml"), "w") as f:
            f.write(
                "screens:\n"
                "  - name: Test\n"
                "    template: status_board\n"
                "    categories:\n"
                "      - name: TestService\n"
                "        url: https://example.com/api/summary.json\n"
                "        type: statuspage\n"
                "        items:\n"
                "          - key: comp1\n"
                "            label: Comp1\n"
                "          - key: comp2\n"
                "            label: Comp2\n"
            )

        cfg = load_config(td)
        assert isinstance(cfg, AppConfig)
        assert cfg.refresh_seconds == 60
        assert cfg.timezone == "UTC"
        assert isinstance(cfg.display, DisplayConfig)
        assert cfg.display.backend == "mock"
        assert cfg.display.full_refresh_every_n_updates == 3
        assert len(cfg.screens) == 1
        s = cfg.screens[0]
        assert s.template == "status_board"
        assert len(s.categories) == 1
        assert s.categories[0].name == "TestService"


def test_load_config_defaults():
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write("backend: mock\n")
        with open(os.path.join(td, "tamagotchai.yml"), "w") as f:
            f.write("refresh_seconds: 60\n")

        cfg = load_config(td)
        assert cfg.refresh_seconds == 60
        assert cfg.display.backend == "mock"
        assert cfg.display.full_refresh_every_n_updates == 50


def test_load_config_invalid_refresh():
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write("backend: mock\n")
        with open(os.path.join(td, "tamagotchai.yml"), "w") as f:
            f.write("refresh_seconds: -1\n")

        with pytest.raises(ValueError, match="refresh_seconds must be positive"):
            load_config(td)


def test_load_config_no_screens(caplog):
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write("backend: mock\n")
        with open(os.path.join(td, "tamagotchai.yml"), "w") as f:
            f.write("refresh_seconds: 300\n")

        with caplog.at_level(logging.WARNING):
            cfg = load_config(td)
        assert len(cfg.screens) == 0
        assert "No screens configured" in caplog.text


def test_load_config_backend_profile_auto_size():
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "display.yml"), "w") as f:
            f.write("backend: waveshare_2in13bc\n")

        cfg = load_config(td)
        assert cfg.display.backend == "waveshare_2in13bc"
        assert cfg.display.width == 104
        assert cfg.display.height == 212


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
