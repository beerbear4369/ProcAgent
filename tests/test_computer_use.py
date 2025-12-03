"""Tests for Computer Use MCP Server."""

import pytest
from unittest.mock import MagicMock, patch

from procagent.cua.computer_use import (
    ComputerUseState,
    get_computer_use_state,
    create_computer_use_tools,
    DEFAULT_WIDTH,
    DEFAULT_HEIGHT,
)


class TestComputerUseState:
    """Tests for ComputerUseState."""

    def test_state_singleton(self):
        """Test ComputerUseState is a singleton."""
        state1 = ComputerUseState()
        state2 = ComputerUseState()
        assert state1 is state2

    def test_default_dimensions(self):
        """Test default screen dimensions."""
        state = get_computer_use_state()
        assert state.screen_width == DEFAULT_WIDTH
        assert state.screen_height == DEFAULT_HEIGHT

    def test_configure(self):
        """Test dimension configuration."""
        state = get_computer_use_state()
        state.configure(1280, 720)
        assert state.screen_width == 1280
        assert state.screen_height == 720
        # Reset
        state.configure(DEFAULT_WIDTH, DEFAULT_HEIGHT)


class TestComputerUseTools:
    """Tests for Computer Use tools."""

    @pytest.fixture
    def tools(self):
        """Create tools."""
        return create_computer_use_tools()

    @pytest.fixture
    def mock_pyautogui(self):
        """Mock pyautogui module."""
        with patch.dict("sys.modules", {"pyautogui": MagicMock()}):
            import sys
            mock = sys.modules["pyautogui"]
            mock.position.return_value = MagicMock(x=100, y=200)
            yield mock

    def test_tools_created(self, tools):
        """Test all expected tools are created."""
        expected_tools = [
            "screenshot", "click", "type", "key",
            "move", "scroll", "drag", "get_mouse_position"
        ]
        for tool_name in expected_tools:
            assert tool_name in tools
            assert callable(tools[tool_name])


class TestToolDescriptions:
    """Test that tools have proper async signatures."""

    def test_all_tools_are_async(self):
        """Test all tools are async functions."""
        import asyncio
        tools = create_computer_use_tools()
        for name, tool in tools.items():
            assert asyncio.iscoroutinefunction(tool), f"{name} should be async"
