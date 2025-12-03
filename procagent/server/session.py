"""
Session Manager for ProcAgent

Manages session lifecycle, VNC port allocation, and cleanup.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger("server.session")


@dataclass
class Session:
    """Represents a user session."""
    session_id: str
    vnc_port: int
    vnc_password: str
    working_dir: Path
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired."""
        elapsed = (datetime.now() - self.last_activity).total_seconds()
        return elapsed > timeout_seconds


class SessionManager:
    """
    Manages ProcAgent sessions.

    For MVP, uses a single fixed VNC instance (no per-session spawning).
    """

    def __init__(
        self,
        base_vnc_port: int = 5900,
        max_sessions: int = 1,  # MVP: single session only
        timeout_seconds: int = 3600,
    ):
        """
        Initialize SessionManager.

        Args:
            base_vnc_port: Fixed VNC port (MVP uses single instance)
            max_sessions: Maximum concurrent sessions (1 for MVP)
            timeout_seconds: Session timeout in seconds
        """
        self.base_vnc_port = base_vnc_port
        self.max_sessions = max_sessions
        self.timeout_seconds = timeout_seconds

        self.sessions: Dict[str, Session] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

        settings = get_settings()
        self.vnc_password = settings.vnc.password
        self.working_base = Path(settings.promax.working_dir)

    async def start(self) -> None:
        """Start the session manager and cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionManager started")

    async def stop(self) -> None:
        """Stop the session manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("SessionManager stopped")

    def create_session(self, session_id: str) -> Session:
        """
        Create a new session.

        Args:
            session_id: Unique session identifier

        Returns:
            Session object

        Raises:
            RuntimeError: If max sessions reached
        """
        if len(self.sessions) >= self.max_sessions:
            raise RuntimeError(
                f"Maximum sessions ({self.max_sessions}) reached. "
                "Please wait for an existing session to end."
            )

        # Create working directory
        working_dir = self.working_base / session_id
        working_dir.mkdir(parents=True, exist_ok=True)

        # Create session (MVP: use fixed VNC port)
        session = Session(
            session_id=session_id,
            vnc_port=self.base_vnc_port,
            vnc_password=self.vnc_password,
            working_dir=working_dir,
        )

        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()
        return session

    async def destroy_session(
        self,
        session_id: str,
        cleanup_files: bool = False
    ) -> None:
        """
        Destroy a session.

        Args:
            session_id: Session to destroy
            cleanup_files: Whether to delete working directory
        """
        session = self.sessions.pop(session_id, None)
        if not session:
            return

        # Optionally clean up working directory
        if cleanup_files and session.working_dir.exists():
            import shutil
            try:
                shutil.rmtree(session.working_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup session files: {e}")

        logger.info(f"Destroyed session: {session_id}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                expired = [
                    sid for sid, session in self.sessions.items()
                    if session.is_expired(self.timeout_seconds)
                ]

                for session_id in expired:
                    logger.info(f"Expiring inactive session: {session_id}")
                    await self.destroy_session(session_id, cleanup_files=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
