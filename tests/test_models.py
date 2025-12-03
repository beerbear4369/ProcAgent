"""Tests for data models."""

import pytest
from datetime import datetime, timedelta

from procagent.models import (
    ProcAgentSession,
    BlockIdentification,
    BlockType,
    StreamSpec,
    StreamProperties,
    ComponentComposition,
    PerformanceTarget,
    SimulationResult,
    SimulationStatus,
    ChatMessage,
    AgentResponse,
    ResponseType,
)


class TestProcAgentSession:
    """Tests for ProcAgentSession model."""

    def test_session_creation(self):
        """Test session is created with defaults."""
        session = ProcAgentSession()
        assert session.session_id is not None
        assert session.vnc_port == 5900
        assert session.project_name is None

    def test_session_update_activity(self):
        """Test activity timestamp update."""
        session = ProcAgentSession()
        old_time = session.last_activity
        session.update_activity()
        assert session.last_activity >= old_time

    def test_session_expiry(self):
        """Test session expiry detection."""
        session = ProcAgentSession()
        # Not expired by default
        assert not session.is_expired(timeout_seconds=3600)

        # Manually set old timestamp
        session.last_activity = datetime.now() - timedelta(hours=2)
        assert session.is_expired(timeout_seconds=3600)


class TestBlockIdentification:
    """Tests for BlockIdentification model."""

    def test_block_identification(self):
        """Test block identification creation."""
        block = BlockIdentification(
            block_type=BlockType.AMINE_TREATER,
            block_name="301-E",
            confidence=0.95,
            from_chat=True
        )
        assert block.block_type == BlockType.AMINE_TREATER
        assert block.confidence == 0.95

    def test_confidence_validation(self):
        """Test confidence must be 0-1."""
        with pytest.raises(ValueError):
            BlockIdentification(
                block_type=BlockType.SEPARATOR,
                block_name="Test",
                confidence=1.5  # Invalid
            )


class TestComponentComposition:
    """Tests for ComponentComposition model."""

    def test_valid_composition(self):
        """Test valid composition that sums to 1.0."""
        comp = ComponentComposition(
            components={
                "Methane": 0.5,
                "Ethane": 0.3,
                "Propane": 0.2
            }
        )
        assert sum(comp.components.values()) == 1.0

    def test_invalid_composition_sum(self):
        """Test composition that doesn't sum to 1.0."""
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ComponentComposition(
                components={
                    "Methane": 0.5,
                    "Ethane": 0.3,
                    # Missing 0.2, total is 0.8
                }
            )

    def test_empty_composition_allowed(self):
        """Test empty composition is allowed."""
        comp = ComponentComposition(components={})
        assert len(comp.components) == 0


class TestStreamProperties:
    """Tests for StreamProperties model."""

    def test_valid_properties(self):
        """Test valid stream properties."""
        props = StreamProperties(
            temperature_c=50.0,
            pressure_kpa=500.0,
            molar_flow_kmol_hr=100.0
        )
        assert props.temperature_c == 50.0

    def test_temperature_range(self):
        """Test temperature must be above absolute zero."""
        with pytest.raises(ValueError):
            StreamProperties(temperature_c=-300.0)  # Below absolute zero

    def test_pressure_positive(self):
        """Test pressure must be positive."""
        with pytest.raises(ValueError):
            StreamProperties(pressure_kpa=-100.0)


class TestStreamSpec:
    """Tests for StreamSpec model."""

    def test_stream_spec_creation(self):
        """Test stream specification creation."""
        stream = StreamSpec(
            name="210_Sour_Offgas",
            stream_type="inlet",
            properties=StreamProperties(
                temperature_c=45.0,
                pressure_kpa=700.0
            )
        )
        assert stream.name == "210_Sour_Offgas"
        assert stream.properties.temperature_c == 45.0


class TestPerformanceTarget:
    """Tests for PerformanceTarget model."""

    def test_target_creation(self):
        """Test performance target creation."""
        target = PerformanceTarget(
            parameter="Offgas H2S",
            target_value=100.0,
            unit="ppm",
            comparison="le"
        )
        assert target.parameter == "Offgas H2S"
        assert target.comparison == "le"


class TestSimulationResult:
    """Tests for SimulationResult model."""

    def test_converged_result(self):
        """Test converged simulation result."""
        result = SimulationResult(
            status=SimulationStatus.CONVERGED,
            solver_status_code=1,
            result_values={"Offgas H2S": 85.0}
        )
        assert result.status == SimulationStatus.CONVERGED
        assert result.result_values["Offgas H2S"] == 85.0

    def test_error_result(self):
        """Test error simulation result."""
        result = SimulationResult(
            status=SimulationStatus.ERROR,
            error_message="Missing inlet specification"
        )
        assert result.status == SimulationStatus.ERROR
        assert "Missing" in result.error_message


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_simple_message(self):
        """Test simple chat message."""
        msg = ChatMessage(message="Create an amine treater")
        assert msg.message == "Create an amine treater"
        assert msg.pfd_image is None

    def test_message_with_image(self):
        """Test message with PFD image."""
        msg = ChatMessage(
            message="Focus on block 301-E",
            pfd_image="base64encodeddata..."
        )
        assert msg.pfd_image is not None


class TestAgentResponse:
    """Tests for AgentResponse model."""

    def test_text_response(self):
        """Test text response."""
        resp = AgentResponse(
            type=ResponseType.TEXT,
            content="Creating amine treater block..."
        )
        assert resp.type == ResponseType.TEXT
        assert resp.content is not None

    def test_session_created_response(self):
        """Test session created response."""
        resp = AgentResponse(
            type=ResponseType.SESSION_CREATED,
            session_id="abc-123"
        )
        assert resp.type == ResponseType.SESSION_CREATED
        assert resp.session_id == "abc-123"
