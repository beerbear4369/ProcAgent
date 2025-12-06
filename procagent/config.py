"""
ProcAgent Configuration Module

Loads settings from config/settings.yaml and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from project root
load_dotenv()


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "127.0.0.1"
    port: int = 8000


class VNCConfig(BaseModel):
    """VNC configuration."""
    host: str = "127.0.0.1"
    port: int = 5900
    password: str = "procagent"
    websockify_port: int = 6080
    novnc_path: str = "./procagent/web/novnc"
    auto_start_websockify: bool = True


class AgentConfig(BaseModel):
    """Claude Agent SDK configuration."""
    model: str = "claude-sonnet-4-5-20250514"
    max_turns: int = 50
    max_budget_usd: float = 10.0


class ProMaxConfig(BaseModel):
    """ProMax configuration."""
    with_gui: bool = True
    working_dir: str = "./projects"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AuthConfig(BaseModel):
    """Authentication configuration."""
    username: str = "procagent"
    password: str = "procagent"
    session_timeout: int = 86400  # 24 hours in seconds


class Settings(BaseModel):
    """Application settings."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    vnc: VNCConfig = Field(default_factory=VNCConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    promax: ProMaxConfig = Field(default_factory=ProMaxConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Settings":
        """Load settings from YAML file and environment variables."""
        if config_path is None:
            # Look for config in standard locations
            possible_paths = [
                Path("config/settings.yaml"),
                Path(__file__).parent.parent / "config" / "settings.yaml",
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break

        config_data: Dict[str, Any] = {}
        if config_path and config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # Override with environment variables
        if os.getenv("PROCAGENT_HOST"):
            config_data.setdefault("server", {})["host"] = os.getenv("PROCAGENT_HOST")
        if os.getenv("PROCAGENT_PORT"):
            config_data.setdefault("server", {})["port"] = int(os.getenv("PROCAGENT_PORT"))
        if os.getenv("VNC_PASSWORD"):
            config_data.setdefault("vnc", {})["password"] = os.getenv("VNC_PASSWORD")
        if os.getenv("ANTHROPIC_API_KEY"):
            # API key is used by Claude Agent SDK directly
            pass
        if os.getenv("PROCAGENT_LOG_LEVEL"):
            config_data.setdefault("logging", {})["level"] = os.getenv("PROCAGENT_LOG_LEVEL")
        if os.getenv("PROCAGENT_AUTH_USERNAME"):
            config_data.setdefault("auth", {})["username"] = os.getenv("PROCAGENT_AUTH_USERNAME")
        if os.getenv("PROCAGENT_AUTH_PASSWORD"):
            config_data.setdefault("auth", {})["password"] = os.getenv("PROCAGENT_AUTH_PASSWORD")

        return cls(**config_data)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings
