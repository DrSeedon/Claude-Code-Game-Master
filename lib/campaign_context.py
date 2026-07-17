"""Safe campaign naming and per-process campaign resolution."""

from __future__ import annotations

import os
from pathlib import Path


CAMPAIGN_ENV = "DM_ACTIVE_CAMPAIGN"
FORBIDDEN_CAMPAIGN_CHARS = frozenset('/\\:*?"<>|')


class InvalidCampaignName(ValueError):
    """Raised when a campaign name cannot safely identify one directory."""


def validate_campaign_name(name: str) -> str:
    normalized = str(name).strip()
    if not normalized:
        raise InvalidCampaignName("Campaign name cannot be empty")
    if (
        normalized in {".", ".."}
        or normalized.startswith(".")
        or ".." in normalized
        or Path(normalized).is_absolute()
        or FORBIDDEN_CAMPAIGN_CHARS.intersection(normalized)
    ):
        raise InvalidCampaignName(f"Invalid campaign name: {name!r}")
    return normalized


def resolve_campaign_dir(
    campaigns_dir: str | Path,
    name: str,
    *,
    must_exist: bool = False,
) -> Path:
    base = Path(campaigns_dir).resolve()
    safe_name = validate_campaign_name(name)
    candidate = (base / safe_name).resolve()
    if candidate.parent != base:
        raise InvalidCampaignName(f"Campaign escapes campaigns directory: {name!r}")
    if must_exist and not candidate.is_dir():
        raise FileNotFoundError(f"Campaign does not exist: {safe_name}")
    return candidate


def scoped_campaign_name(world_state_dir: str | Path) -> str | None:
    override = os.environ.get(CAMPAIGN_ENV, "").strip()
    if override:
        return validate_campaign_name(override)

    active_file = Path(world_state_dir) / "active-campaign.txt"
    if not active_file.exists():
        return None
    active = active_file.read_text(encoding="utf-8").strip()
    return validate_campaign_name(active) if active else None
