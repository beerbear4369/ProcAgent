"""
ProcAgent Data Models

Pydantic models for sessions, streams, simulation, and WebSocket messages.
"""

from .session import ProcAgentSession
from .promax import (
    BlockIdentification,
    BlockType,
    StreamSpec,
    StreamProperties,
    ComponentComposition,
    PerformanceTarget,
    SimulationResult,
    SimulationStatus,
    ResultsComparison,
    TargetAssessment,
    AdjustmentSuggestion,
)
from .messages import (
    ChatMessage,
    AgentResponse,
    ResponseType,
    ToolUseInfo,
    ResultsInfo,
)

__all__ = [
    # Session
    "ProcAgentSession",
    # ProMax
    "BlockIdentification",
    "BlockType",
    "StreamSpec",
    "StreamProperties",
    "ComponentComposition",
    "PerformanceTarget",
    "SimulationResult",
    "SimulationStatus",
    "ResultsComparison",
    "TargetAssessment",
    "AdjustmentSuggestion",
    # Messages
    "ChatMessage",
    "AgentResponse",
    "ResponseType",
    "ToolUseInfo",
    "ResultsInfo",
]
