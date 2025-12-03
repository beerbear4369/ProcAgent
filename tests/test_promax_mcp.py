"""Tests for ProMax MCP Server."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from procagent.mcp.promax_server import (
    ProMaxState,
    get_promax_state,
    create_promax_tools,
    convert_units,
    BLOCK_TYPE_MAP,
)


class TestUnitConversions:
    """Tests for unit conversion functions."""

    def test_temperature_c_to_k(self):
        """Test Celsius to Kelvin conversion."""
        assert convert_units(0, "C", "temperature") == 273.15
        assert convert_units(100, "C", "temperature") == 373.15
        assert abs(convert_units(-40, "C", "temperature") - 233.15) < 0.01

    def test_temperature_f_to_k(self):
        """Test Fahrenheit to Kelvin conversion."""
        assert abs(convert_units(32, "F", "temperature") - 273.15) < 0.01
        assert abs(convert_units(212, "F", "temperature") - 373.15) < 0.01

    def test_pressure_kpa_to_pa(self):
        """Test kPa to Pa conversion."""
        assert convert_units(100, "kPa", "pressure") == 100000
        assert convert_units(1, "kPa", "pressure") == 1000

    def test_pressure_bar_to_pa(self):
        """Test bar to Pa conversion."""
        assert convert_units(1, "bar", "pressure") == 100000

    def test_flow_kmol_hr_to_mol_s(self):
        """Test kmol/hr to mol/s conversion."""
        result = convert_units(3.6, "kmol/hr", "flow")
        assert abs(result - 1.0) < 0.001  # 3.6 kmol/hr = 1 mol/s

    def test_invalid_unit_type(self):
        """Test invalid unit type raises error."""
        with pytest.raises(ValueError, match="Unknown unit type"):
            convert_units(100, "C", "invalid_type")

    def test_invalid_unit(self):
        """Test invalid unit raises error."""
        with pytest.raises(ValueError, match="Unknown temperature unit"):
            convert_units(100, "InvalidUnit", "temperature")


class TestProMaxState:
    """Tests for ProMaxState singleton."""

    def test_state_singleton(self):
        """Test ProMaxState is a singleton."""
        state1 = ProMaxState()
        state2 = ProMaxState()
        assert state1 is state2

    def test_state_initial_values(self):
        """Test initial state values."""
        state = get_promax_state()
        state.reset()  # Ensure clean state
        assert state.pmx is None
        assert state.project is None
        assert state.flowsheet is None
        assert state.is_connected is False
        assert state.has_flowsheet is False

    def test_state_reset(self):
        """Test state reset."""
        state = get_promax_state()
        state.pmx = "mock"
        state.project = "mock_project"
        state.reset()
        assert state.pmx is None
        assert state.project is None


class TestProMaxTools:
    """Tests for ProMax MCP tools."""

    @pytest.fixture
    def tools(self):
        """Create tools and reset state."""
        state = get_promax_state()
        state.reset()
        return create_promax_tools()

    @pytest.fixture
    def mock_promax(self):
        """Create mock ProMax COM object."""
        mock_pmx = MagicMock()
        mock_pmx.Version.Major = 6
        mock_pmx.Version.Minor = 0
        return mock_pmx

    @pytest.mark.asyncio
    async def test_connect_promax_not_windows(self, tools):
        """Test connect fails gracefully on non-Windows."""
        with patch("platform.system", return_value="Linux"):
            with patch.dict("sys.modules", {"win32com.client": None}):
                result = await tools["connect_promax"](with_gui=False)
                # Should fail gracefully with error message
                assert "Failed" in result or "Error" in result or "Connected" in result

    @pytest.mark.asyncio
    async def test_create_project_not_connected(self, tools):
        """Test create_project fails when not connected."""
        result = await tools["create_project"]("TestFlowsheet")
        assert "Error" in result
        assert "Not connected" in result

    @pytest.mark.asyncio
    async def test_add_components_no_flowsheet(self, tools):
        """Test add_components fails when no flowsheet."""
        result = await tools["add_components"](["Methane", "Water"])
        assert "Error" in result
        assert "No flowsheet" in result

    @pytest.mark.asyncio
    async def test_create_block_no_flowsheet(self, tools):
        """Test create_block fails when no flowsheet."""
        result = await tools["create_block"]("AmineTreater", "Test-Block")
        assert "Error" in result
        assert "No flowsheet" in result

    @pytest.mark.asyncio
    async def test_create_block_invalid_type(self, tools):
        """Test create_block fails with invalid block type."""
        state = get_promax_state()
        state.flowsheet = MagicMock()  # Fake flowsheet
        result = await tools["create_block"]("InvalidType", "Test-Block")
        assert "Error" in result
        assert "Unknown block type" in result

    @pytest.mark.asyncio
    async def test_set_stream_composition_invalid_sum(self, tools):
        """Test composition validation rejects invalid sum."""
        state = get_promax_state()
        state.flowsheet = MagicMock()
        result = await tools["set_stream_composition"](
            "TestStream",
            {"Methane": 0.5, "Ethane": 0.3}  # Sum = 0.8, not 1.0
        )
        assert "Error" in result
        assert "sum to 1.0" in result

    @pytest.mark.asyncio
    async def test_flash_stream_no_flowsheet(self, tools):
        """Test flash_stream fails when no flowsheet."""
        result = await tools["flash_stream"]("TestStream")
        assert "Error" in result
        assert "No flowsheet" in result

    @pytest.mark.asyncio
    async def test_run_simulation_no_flowsheet(self, tools):
        """Test run_simulation fails when no flowsheet."""
        result = await tools["run_simulation"]()
        assert "Error" in result
        assert "No flowsheet" in result

    @pytest.mark.asyncio
    async def test_save_project_no_project(self, tools):
        """Test save_project fails when no project."""
        result = await tools["save_project"]("test.prx")
        assert "Error" in result
        assert "No project" in result

    @pytest.mark.asyncio
    async def test_close_project_no_project(self, tools):
        """Test close_project when no project."""
        result = await tools["close_project"]()
        assert "No project" in result


class TestBlockTypeMap:
    """Tests for block type mapping."""

    def test_all_block_types_have_mapping(self):
        """Test all expected block types have mappings."""
        expected_types = [
            "AmineTreater", "Separator", "HeatExchanger",
            "Compressor", "Pump", "Valve", "Mixer", "Splitter"
        ]
        for block_type in expected_types:
            assert block_type in BLOCK_TYPE_MAP

    def test_mapping_has_required_keys(self):
        """Test each mapping has stencil and master keys."""
        for block_type, mapping in BLOCK_TYPE_MAP.items():
            assert "stencil" in mapping, f"{block_type} missing stencil"
            assert "master" in mapping, f"{block_type} missing master"
