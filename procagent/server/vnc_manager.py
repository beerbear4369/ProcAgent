"""
VNC Manager - Manages websockify subprocess lifecycle.

websockify serves as a WebSocket-to-TCP proxy that:
1. Serves noVNC HTML files at http://localhost:6080/vnc.html
2. Proxies WebSocket connections to TightVNC server at port 5900
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger("server.vnc_manager")


class WebsockifyManager:
    """Manages websockify subprocess for VNC WebSocket proxy."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._settings = get_settings()

    def start(self) -> bool:
        """
        Start websockify subprocess with noVNC web server.

        Returns:
            True if started successfully, False otherwise.
        """
        if self._process is not None and self._process.poll() is None:
            logger.warning("websockify already running (PID %d)", self._process.pid)
            return True

        vnc_config = self._settings.vnc
        novnc_path = Path(vnc_config.novnc_path).resolve()

        if not novnc_path.exists():
            logger.error("noVNC path not found: %s", novnc_path)
            logger.error("Please download noVNC to %s", novnc_path)
            return False

        # Check for vnc.html
        vnc_html = novnc_path / "vnc.html"
        if not vnc_html.exists():
            logger.error("vnc.html not found in %s", novnc_path)
            return False

        # Build websockify command
        # websockify --web=<novnc_path> <listen_port> <vnc_host>:<vnc_port>
        cmd = [
            sys.executable,
            "-m",
            "websockify",
            f"--web={novnc_path}",
            str(vnc_config.websockify_port),
            f"{vnc_config.host}:{vnc_config.port}",
        ]

        logger.info("Starting websockify: %s", " ".join(cmd))

        try:
            # Start as subprocess (not blocking)
            # Use CREATE_NEW_PROCESS_GROUP on Windows for proper cleanup
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
            logger.info("websockify started with PID %d", self._process.pid)
            logger.info(
                "noVNC available at http://localhost:%d/vnc.html",
                vnc_config.websockify_port,
            )
            return True

        except FileNotFoundError:
            logger.error(
                "websockify not found. Install with: pip install websockify"
            )
            return False
        except Exception as e:
            logger.error("Failed to start websockify: %s", e)
            return False

    def stop(self) -> None:
        """Stop websockify subprocess."""
        if self._process is None:
            return

        logger.info("Stopping websockify (PID %d)", self._process.pid)

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
                logger.info("websockify terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("websockify did not terminate, killing")
                self._process.kill()
                self._process.wait()
        except Exception as e:
            logger.error("Error stopping websockify: %s", e)
        finally:
            self._process = None

    def is_running(self) -> bool:
        """Check if websockify is running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def get_status(self) -> dict:
        """Get websockify status information."""
        vnc_config = self._settings.vnc
        return {
            "running": self.is_running(),
            "pid": self._process.pid if self._process else None,
            "websockify_port": vnc_config.websockify_port,
            "vnc_target": f"{vnc_config.host}:{vnc_config.port}",
            "novnc_url": f"http://localhost:{vnc_config.websockify_port}/vnc.html",
        }


# Singleton instance
_manager: Optional[WebsockifyManager] = None


def get_websockify_manager() -> WebsockifyManager:
    """Get the global websockify manager instance."""
    global _manager
    if _manager is None:
        _manager = WebsockifyManager()
    return _manager
