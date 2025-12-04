"""
ProcAgent Logging Configuration

Sets up structured logging for all components.
"""

import logging
import sys
from typing import Optional

from .config import get_settings


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration for ProcAgent.

    Args:
        level: Optional override for log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Root logger for ProcAgent
    """
    settings = get_settings()
    log_level = level or settings.logging.level
    log_format = settings.logging.format

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Create ProcAgent logger
    logger = logging.getLogger("procagent")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Also enable Claude Agent SDK logging at DEBUG level
    if log_level.upper() == "DEBUG":
        logging.getLogger("claude_agent_sdk").setLevel(logging.DEBUG)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific component.

    Args:
        name: Component name (e.g., 'agent', 'mcp.promax', 'server')

    Returns:
        Logger instance
    """
    return logging.getLogger(f"procagent.{name}")
