"""Campaign management API for DM Game Master web client.

Provides functions for listing, creating, deleting and activating campaigns.
All data is stored in world-state/campaigns/ on disk.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import get_project_root


# ─────────────────────────── Helper Functions ──────────────────────────────────

def _get_campaigns_dir() -> Path:
    """Return path to all campaigns directory."""
    return get_project_root() / "world-state" / "campaigns"


def _get_active_campaign_file() -> Path:
    """Return path to active campaign name file."""
    return get_project_root() / "world-state" / "active-campaign.txt"


def _read_campaign_overview(campaign_dir: Path) -> Dict:
    """Read campaign-overview.json for campaign.

    Args:
        campaign_dir: Path to campaign directory

    Returns:
        Dict with metadata or empty dict if file missing
    """
    overview_file = campaign_dir / "campaign-overview.json"
    if overview_file.exists():
        try:
            return json.loads(overview_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _campaign_to_info(campaign_name: str, campaigns_dir: Path, active_name: Optional[str]) -> Dict:
    """Build info dict for single campaign.

    Args:
        campaign_name: Campaign name (subdirectory name)
        campaigns_dir: Path to campaigns root directory
        active_name: Current active campaign name (or None)

    Returns:
        Dict with fields: name, active, created_at, genre, tone, description
    """
    campaign_dir = campaigns_dir / campaign_name
    overview = _read_campaign_overview(campaign_dir)

    return {
        "name": campaign_name,
        "active": campaign_name == active_name,
        "created_at": overview.get("created_at", ""),
        "genre": overview.get("genre", ""),
        "tone": overview.get("tone", ""),
        "description": overview.get("description", ""),
    }


# ─────────────────────────── Public Functions ──────────────────────────────────

def list_campaigns() -> List[Dict]:
    """Get list of all available campaigns.

    Returns:
        List of dicts with information about each campaign:
            - name (str): Campaign name
            - active (bool): Whether campaign is active
            - created_at (str): Creation date (from campaign-overview.json)
            - genre (str): Campaign genre
            - tone (str): Campaign tone/atmosphere
            - description (str): Campaign description
    """
    campaigns_dir = _get_campaigns_dir()
    campaigns_dir.mkdir(parents=True, exist_ok=True)

    # Determine active campaign
    active_name = _get_active_campaign_name()

    campaigns = []
    for entry in sorted(campaigns_dir.iterdir()):
        if entry.is_dir():
            campaigns.append(_campaign_to_info(entry.name, campaigns_dir, active_name))

    return campaigns


def _get_active_campaign_name() -> Optional[str]:
    """Return current active campaign name or None."""
    active_file = _get_active_campaign_file()
    if active_file.exists():
        name = active_file.read_text(encoding="utf-8").strip()
        campaign_dir = _get_campaigns_dir() / name
        if name and campaign_dir.exists():
            return name
    return None


def create_campaign(
    name: str,
    genre: str = "",
    tone: str = "",
    description: str = "",
    modules: Optional[List[str]] = None,
    narrator_style: str = "",
) -> Dict:
    """Create new campaign.

    Creates campaign directory and basic campaign-overview.json.

    Args:
        name: Campaign name (used as directory name)
        genre: Campaign genre (e.g. "fantasy", "sci-fi")
        tone: Campaign tone (e.g. "dark", "heroic")
        description: Brief campaign description
        modules: List of active modules
        narrator_style: Narrator style

    Returns:
        Dict with created campaign info or error:
            - success (bool): Operation success
            - name (str): Campaign name (on success)
            - error (str): Error message (on failure)

    Raises:
        ValueError: If campaign name contains invalid characters
    """
    # Validate name
    if not name or not name.strip():
        return {"success": False, "error": "Campaign name cannot be empty"}

    # Allow only safe characters for directory name
    safe_name = name.strip()
    forbidden = set('/\\:*?"<>|')
    if any(c in forbidden for c in safe_name):
        return {
            "success": False,
            "error": f"Campaign name contains invalid characters: {forbidden & set(safe_name)}",
        }

    campaigns_dir = _get_campaigns_dir()
    campaigns_dir.mkdir(parents=True, exist_ok=True)

    campaign_dir = campaigns_dir / safe_name
    if campaign_dir.exists():
        return {"success": False, "error": f"Campaign '{safe_name}' already exists"}

    # Create directory structure
    campaign_dir.mkdir(parents=True)

    # Build campaign-overview.json
    overview = {
        "name": safe_name,
        "genre": genre,
        "tone": tone,
        "description": description,
        "modules": modules or [],
        "narrator_style": narrator_style,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "calendar": {},
        "currency": {},
    }

    overview_file = campaign_dir / "campaign-overview.json"
    overview_file.write_text(
        json.dumps(overview, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Create empty world.json
    world_file = campaign_dir / "world.json"
    world_file.write_text(
        json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Create empty session-log.md
    session_log = campaign_dir / "session-log.md"
    session_log.write_text(f"# Session Log: {safe_name}\n", encoding="utf-8")

    return {
        "success": True,
        "name": safe_name,
        "genre": genre,
        "tone": tone,
        "description": description,
        "created_at": overview["created_at"],
        "active": False,
    }


def delete_campaign(name: str) -> Dict:
    """Delete campaign and all its data.

    Args:
        name: Campaign name to delete

    Returns:
        Dict with result:
            - success (bool): Operation success
            - error (str): Error message (on failure)
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"success": False, "error": f"Campaign '{name}' not found"}

    # Prevent deleting active campaign
    active_name = _get_active_campaign_name()
    if active_name == name:
        return {
            "success": False,
            "error": f"Cannot delete active campaign '{name}'. Activate another first.",
        }

    try:
        shutil.rmtree(campaign_dir)
    except OSError as e:
        return {"success": False, "error": f"Deletion error: {str(e)}"}

    return {"success": True}


def activate_campaign(name: str) -> Dict:
    """Set active campaign.

    Writes name to world-state/active-campaign.txt.

    Args:
        name: Campaign name to activate

    Returns:
        Dict with result:
            - success (bool): Operation success
            - name (str): Activated campaign name (on success)
            - error (str): Error message (on failure)
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"success": False, "error": f"Campaign '{name}' not found"}

    active_file = _get_active_campaign_file()
    active_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        active_file.write_text(name, encoding="utf-8")
    except OSError as e:
        return {"success": False, "error": f"Error writing active campaign: {str(e)}"}

    return {"success": True, "name": name}


def get_campaign(name: str) -> Dict:
    """Get information about single campaign.

    Args:
        name: Campaign name

    Returns:
        Dict with campaign info or error
    """
    campaigns_dir = _get_campaigns_dir()
    campaign_dir = campaigns_dir / name

    if not campaign_dir.exists():
        return {"error": f"Campaign '{name}' not found"}

    active_name = _get_active_campaign_name()
    return _campaign_to_info(name, campaigns_dir, active_name)
