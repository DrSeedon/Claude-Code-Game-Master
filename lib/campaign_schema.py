"""Canonical campaign metadata and player-node builders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


CAMPAIGN_SCHEMA_VERSION = 2


def build_campaign_overview(
    slug: str,
    display_name: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the one metadata shape used by CLI, web, and campaign tools."""
    overview: dict[str, Any] = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "name": slug,
        "campaign_name": display_name,
        "genre": "Fantasy",
        "tone": "",
        "description": "",
        "modules": {},
        "narrator_style": "",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "current_date": "1st of the First Month, Year 1",
        "precise_time": "08:00",
        "time_of_day": "Morning",
        "player_position": {
            "current_location": None,
            "previous_location": None,
        },
        "current_character": None,
        "session_count": 0,
        "play_mode": "interactive",
        "cinematic_visuals": {
            "enabled": True,
            "frequency": "occasional",
            "aspect_ratio": "16:9",
            "presentation": "game-loading-screen",
        },
        "calendar": {},
        "currency": {},
    }
    if overrides:
        overview.update(overrides)

    modules = overview.get("modules")
    if isinstance(modules, list):
        overview["modules"] = {module_id: True for module_id in modules}
    elif not isinstance(modules, dict):
        overview["modules"] = {}

    overview["schema_version"] = CAMPAIGN_SCHEMA_VERSION
    overview["name"] = slug
    overview["campaign_name"] = overview.get("campaign_name") or display_name
    return overview


def build_player_data(character: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Normalize player data so mutable gameplay fields stay under node.data."""
    name = str(character.get("name") or "Hero")
    data = {key: value for key, value in character.items() if key != "name"}
    level = int(data.get("level", 1))
    data["level"] = max(1, level)
    data.setdefault("race", "")
    data.setdefault("class", "")
    data.setdefault("hp", {"current": 10, "max": 10})
    data.setdefault("xp", 0)
    data.setdefault("money", data.pop("gold", 0))
    return name, data
