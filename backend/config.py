"""Configuration module for DM Game Master backend."""

import os
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from lib.campaign_context import (
    InvalidCampaignName,
    resolve_campaign_dir,
    scoped_campaign_name,
)

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Project paths (required) - MUST be first (no defaults)
    project_root: Path
    world_state_base: Path
    campaigns_dir: Path

    # Claude SDK settings
    model_name: str = "claude-sonnet-5"

    # Backend server settings
    backend_host: str = "127.0.0.1"
    backend_port: int = 18083

    # Active campaign paths (set after initialization)
    campaign_name: Optional[str] = None
    campaign_dir: Optional[Path] = None
    world_file: Optional[Path] = None
    session_log: Optional[Path] = None
    campaign_overview: Optional[Path] = None


def get_project_root() -> Path:
    """Get project root directory (parent of backend/)."""
    return Path(__file__).parent.parent.absolute()


def get_active_campaign() -> Optional[str]:
    """Get active campaign name from world-state/active-campaign.txt."""
    project_root = get_project_root()
    world_state = project_root / "world-state"
    try:
        campaign_name = scoped_campaign_name(world_state)
        if not campaign_name:
            return None
        resolve_campaign_dir(
            world_state / "campaigns", campaign_name, must_exist=True
        )
        return campaign_name
    except (InvalidCampaignName, FileNotFoundError):
        return None


def get_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Config: Application configuration
    """
    # Get project paths
    project_root = get_project_root()
    world_state_base = project_root / "world-state"
    campaigns_dir = world_state_base / "campaigns"

    # Create base directories if they don't exist
    world_state_base.mkdir(exist_ok=True)
    campaigns_dir.mkdir(exist_ok=True)

    # Get active campaign
    campaign_name = get_active_campaign()

    # Build config
    config = Config(
        project_root=project_root,
        world_state_base=world_state_base,
        campaigns_dir=campaigns_dir,
        model_name=os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-5",
        backend_host=os.environ.get("BACKEND_HOST") or "127.0.0.1",
        backend_port=int(os.environ.get("BACKEND_PORT", "18083")),
    )

    # Set campaign-specific paths if active campaign exists
    if campaign_name:
        config.campaign_name = campaign_name
        config.campaign_dir = campaigns_dir / campaign_name
        config.world_file = config.campaign_dir / "world.json"
        config.session_log = config.campaign_dir / "session-log.md"
        config.campaign_overview = config.campaign_dir / "campaign-overview.json"

    return config


def validate_server_security(config: Config, password: str | None = None) -> None:
    """Refuse unauthenticated exposure beyond the local machine."""
    host = config.backend_host.strip().lower()
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host == "localhost"
    password = password if password is not None else os.environ.get("DND_AUTH_PASSWORD")
    if not is_loopback and not password:
        raise RuntimeError(
            "DND_AUTH_PASSWORD is required when BACKEND_HOST is not loopback"
        )
