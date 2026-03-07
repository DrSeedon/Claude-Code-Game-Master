import pytest
import json
from pathlib import Path


@pytest.fixture
def minimal_campaign(tmp_path):
    campaign_dir = tmp_path / "minimal-campaign"
    campaign_dir.mkdir()

    overview = {
        "campaign_name": "Minimal Test",
        "time_of_day": "Day",
        "precise_time": "12:00",
        "current_date": "Day 1"
    }
    with open(campaign_dir / "campaign-overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)

    return campaign_dir


@pytest.fixture
def stalker_campaign(tmp_path):
    campaign_dir = tmp_path / "stalker-campaign"
    campaign_dir.mkdir()

    overview = {
        "campaign_name": "STALKER Test",
        "time_of_day": "Morning",
        "precise_time": "08:00",
        "current_date": "April 15th, 2012",
        "current_character": "Stalker",
        "campaign_rules": {}
    }
    with open(campaign_dir / "campaign-overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, indent=2, ensure_ascii=False)

    module_data = campaign_dir / "module-data"
    module_data.mkdir(parents=True, exist_ok=True)
    custom_stats_config = {
        "enabled": True,
        "character_stats": {
            "hunger": {"current": 80, "max": 100},
            "thirst": {"current": 70, "max": 100},
            "radiation": {"current": 0, "max": 500},
            "awareness": {"current": 55, "max": 100}
        },
        "rules": [
            {"stat": "hunger", "per_hour": -2, "min": 0, "max": 100},
            {"stat": "thirst", "per_hour": -3, "min": 0, "max": 100},
            {"stat": "radiation", "per_hour": -1, "min": 0, "max": 500}
        ]
    }
    with open(module_data / "custom-stats.json", "w", encoding="utf-8") as f:
        json.dump(custom_stats_config, f, indent=2, ensure_ascii=False)

    character = {
        "name": "Stalker",
        "speed_kmh": 4,
        "hp": {"current": 25, "max": 25},
        "skills": {
            "Survival": 3,
            "Perception": 3
        },
        "abilities": {
            "dex": 14,
            "wis": 12
        }
    }
    with open(campaign_dir / "character.json", "w", encoding="utf-8") as f:
        json.dump(character, f, indent=2, ensure_ascii=False)

    locations = {
        "Cordon": {
            "coordinates": {"x": 0, "y": 0},
            "diameter_meters": 100,
            "connections": [
                {
                    "to": "Junkyard",
                    "distance_meters": 2000,
                    "bearing": 0,
                    "terrain": "open"
                }
            ]
        },
        "Junkyard": {
            "coordinates": {"x": 0, "y": 2000},
            "diameter_meters": 300,
            "connections": [
                {
                    "to": "Cordon",
                    "distance_meters": 2000,
                    "bearing": 180,
                    "terrain": "open"
                }
            ]
        }
    }
    with open(campaign_dir / "locations.json", "w", encoding="utf-8") as f:
        json.dump(locations, f, indent=2, ensure_ascii=False)

    return campaign_dir
