"""
WebSocket message models for client-server communication.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """Types of responses sent to the client."""
    SESSION_CREATED = "session_created"
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    RESULTS = "results"
    ERROR = "error"
    STATUS = "status"


class ChatMessage(BaseModel):
    """Message from client to server."""

    message: str
    pfd_image: Optional[str] = Field(
        default=None,
        description="Base64-encoded PFD image"
    )
    stream_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Stream data JSON"
    )
    timestamp: datetime = Field(default_factory=datetime.now)


class ToolUseInfo(BaseModel):
    """Information about a tool being used."""

    tool_name: str
    tool_input: Dict[str, Any]
    tool_id: Optional[str] = None


class ResultsInfo(BaseModel):
    """Simulation results information."""

    parameters: List[Dict[str, Any]]  # [{name, target, actual, unit, passed}]
    overall_pass: bool
    suggestions: Optional[List[Dict[str, str]]] = None


class AgentResponse(BaseModel):
    """Response from server to client."""

    type: ResponseType
    content: Optional[str] = None

    # For session_created
    session_id: Optional[str] = None

    # For tool_use
    tool_info: Optional[ToolUseInfo] = None

    # For results
    results_info: Optional[ResultsInfo] = None

    # For status updates
    status: Optional[str] = None

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
