"""
Session models for ProcAgent.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ProcAgentSession(BaseModel):
    """Represents a ProcAgent user session."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)

    # VNC connection info
    vnc_host: str = "127.0.0.1"
    vnc_port: int = 5900
    vnc_password: str = "procagent"

    # Working directory for this session
    working_dir: Optional[Path] = None

    # ProMax project state
    project_name: Optional[str] = None
    flowsheet_name: Optional[str] = None

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_seconds: int = 3600) -> bool:
        """Check if session has expired."""
        elapsed = (datetime.now() - self.last_activity).total_seconds()
        return elapsed > timeout_seconds
