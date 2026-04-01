"""Configuration module for DM Game Master backend."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Project paths (required) - MUST be first (no defaults)
    project_root: Path
    world_state_base: Path
    campaigns_dir: Path

    # AI Provider settings (optional) - with defaults
    ai_provider: str = "auto"  # "auto", "api", "sdk"
    anthropic_api_key: Optional[str] = None  # Required only for "api" provider

    # Anthropic API settings (optional)
    model_name: str = "claude-3-5-sonnet-20241022"

    # Backend server settings
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

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
    active_file = project_root / "world-state" / "active-campaign.txt"

    if active_file.exists():
        campaign_name = active_file.read_text().strip()
        campaign_dir = project_root / "world-state" / "campaigns" / campaign_name
        if campaign_name and campaign_dir.exists():
            return campaign_name

    return None


def get_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Config: Application configuration

    Raises:
        ValueError: If AI_PROVIDER=api but ANTHROPIC_API_KEY is not set
    """
    # Определяем тип AI провайдера
    ai_provider = os.environ.get("AI_PROVIDER", "auto")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Валидация: если явно выбран API провайдер, ключ обязателен
    if ai_provider == "api" and not api_key:
        raise ValueError(
            "AI_PROVIDER=api требует ANTHROPIC_API_KEY в .env файле.\n"
            "Или используйте AI_PROVIDER=sdk для работы через подписку."
        )

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
        ai_provider=ai_provider,
        anthropic_api_key=api_key,  # Может быть None для SDK провайдера
        project_root=project_root,
        world_state_base=world_state_base,
        campaigns_dir=campaigns_dir,
        model_name=os.environ.get("ANTHROPIC_MODEL") or "claude-3-5-sonnet-20241022",
        backend_host=os.environ.get("BACKEND_HOST") or "0.0.0.0",
        backend_port=int(os.environ.get("BACKEND_PORT", "8000")),
    )

    # Set campaign-specific paths if active campaign exists
    if campaign_name:
        config.campaign_name = campaign_name
        config.campaign_dir = campaigns_dir / campaign_name
        config.world_file = config.campaign_dir / "world.json"
        config.session_log = config.campaign_dir / "session-log.md"
        config.campaign_overview = config.campaign_dir / "campaign-overview.json"

    return config
