"""Tests for configuration module."""

import pytest
from pathlib import Path

from procagent.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.server.host == "127.0.0.1"
        assert settings.server.port == 8000
        assert settings.vnc.port == 5900
        assert settings.agent.max_turns == 50

    def test_load_from_dict(self):
        """Test loading settings from dictionary."""
        data = {
            "server": {"port": 9000},
            "agent": {"max_budget_usd": 5.0}
        }
        settings = Settings(**data)
        assert settings.server.port == 9000
        assert settings.agent.max_budget_usd == 5.0
        # Defaults should still work
        assert settings.server.host == "127.0.0.1"

    def test_get_settings_singleton(self):
        """Test that get_settings returns consistent instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2
