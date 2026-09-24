"""
generation/config.py

Responsible ONLY for:
- Loading .env
- Validating required environment variables
- Exposing configuration as a typed Config object

No application logic here. No selectors. No URLs hardcoded.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv


# All required environment variable names
REQUIRED_VARS = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "UI_BASE_URL",
    "API_BASE_URL",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    "ADMIN_PATH",
    "MCP_COMMAND",
    "MCP_PACKAGE",
    "API_TIMEOUT",
    "HEADLESS",
    "UI_EVIDENCE_TIMEOUT",
    "UI_POLL_INTERVAL",
]


@dataclass
class Config:
    """All configuration loaded from .env. No defaults for secrets."""

    # Gemini AI
    gemini_api_key: str
    gemini_model: str

    # Application URLs
    ui_base_url: str
    api_base_url: str

    # Admin credentials
    admin_username: str
    admin_password: str
    admin_path: str

    # MCP settings
    mcp_command: str
    mcp_package: str

    # Browser settings
    headless: bool

    # Timeouts
    api_timeout: int
    ui_evidence_timeout: int
    ui_poll_interval: int


def load_config() -> Config:
    """
    Load and validate all configuration from the .env file.

    Uses override=True so .env values always take precedence over
    system environment variables (important in IDE environments).

    Raises:
        EnvironmentError: If required variables are missing.
    """
    load_dotenv(override=True)  # .env takes precedence over system env

    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please copy .env.example to .env and fill in all values."
        )

    return Config(
        gemini_api_key=os.environ["GEMINI_API_KEY"],
        gemini_model=os.environ["GEMINI_MODEL"],
        ui_base_url=os.environ["UI_BASE_URL"].rstrip("/"),
        api_base_url=os.environ["API_BASE_URL"].rstrip("/"),
        admin_username=os.environ["ADMIN_USERNAME"],
        admin_password=os.environ["ADMIN_PASSWORD"],
        admin_path=os.environ["ADMIN_PATH"],
        mcp_command=os.environ["MCP_COMMAND"],
        mcp_package=os.environ["MCP_PACKAGE"],
        headless=os.environ["HEADLESS"].lower() in ("true", "1", "yes"),
        api_timeout=int(os.environ["API_TIMEOUT"]),
        ui_evidence_timeout=int(os.environ["UI_EVIDENCE_TIMEOUT"]),
        ui_poll_interval=int(os.environ["UI_POLL_INTERVAL"]),
    )
