"""Ready-campaign blueprint and wizard creation-rule tests."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.campaign_api import create_campaign
from backend.campaign_setup import (
    CampaignSetupError,
    load_creation_context,
    validate_campaign_setup,
)
from backend.config import get_project_root
from backend.wizard_mcp import WizardEvents, run_wizard_tool


def ready_setup() -> dict:
    nodes = [
        {
            "id": f"location:area-{index}",
            "type": "location",
            "name": f"Area {index}",
            "data": {"description": f"Starting region area {index}."},
        }
        for index in range(1, 5)
    ]
    nodes.extend(
        {
            "id": f"npc:contact-{index}",
            "type": "npc",
            "name": f"Contact {index}",
            "data": {
                "description": f"Campaign contact number {index}.",
                "attitude": "neutral",
            },
        }
        for index in range(1, 7)
    )
    nodes.extend(
        {
            "id": f"quest:hook-{index}",
            "type": "quest",
            "name": f"Hook {index}",
            "data": {
                "quest_type": "main",
                "description": f"Story hook {index}.",
                "status": "active",
                "objectives": [{"text": "Investigate", "done": False}],
            },
        }
        for index in range(1, 4)
    )
    nodes.extend(
        {
            "id": f"consequence:event-{index}",
            "type": "consequence",
            "name": f"Event {index}",
            "data": {
                "description": f"Scheduled event {index}.",
                "trigger": f"{index} days",
                "status": "pending",
            },
        }
        for index in range(1, 4)
    )
    nodes.append(
        {
            "id": "misc:economy",
            "type": "misc",
            "name": "Economy",
            "data": {
                "expenses": [],
                "income": [],
                "production": [],
                "random_events": {"enabled": False},
            },
        }
    )

    edges = [
        {
            "from": "location:area-1",
            "to": f"location:area-{index}",
            "type": "connected",
            "data": {"path": "A maintained route."},
        }
        for index in range(2, 5)
    ]
    edges.extend(
        {
            "from": f"npc:contact-{index}",
            "to": "location:area-1",
            "type": "at",
        }
        for index in range(1, 7)
    )

    return {
        "starting_location_id": "location:area-1",
        "overview": {
            "current_date": "20 July 2500",
            "precise_time": "08:00",
            "time_of_day": "Morning",
            "currency": {
                "base": "credit",
                "denominations": [
                    {
                        "id": "credit",
                        "name": "Credit",
                        "symbol": "₡",
                        "rate": 1,
                    }
                ],
            },
            "calendar": {},
        },
        "player": {
            "data": {
                "race": "Human",
                "class": "Commander",
                "background": "Veteran",
                "level": 1,
                "hp": {"current": 12, "max": 12},
                "ac": 14,
                "xp": {"current": 0, "next_level": 300},
                "money": 0,
                "proficiency_bonus": 2,
                "stats": {
                    "str": 12,
                    "dex": 14,
                    "con": 14,
                    "int": 15,
                    "wis": 13,
                    "cha": 10,
                },
                "skills": {"command": 4},
                "saves": {"str": 1, "dex": 2, "con": 2, "int": 4, "wis": 1, "cha": 0},
                "save_proficiencies": ["int", "con"],
                "conditions": [],
                "equipment": {
                    "armor": {"name": "Field jacket", "ac": 14},
                    "weapons": [{"name": "Service sidearm", "damage": "1d8"}],
                },
                "features": ["Command presence"],
            },
            "inventory": {
                "stackable": {"Rations": {"qty": 3, "weight": 0.5}},
                "unique": ["Command datapad"],
            },
        },
        "nodes": nodes,
        "edges": edges,
        "module_data": {},
        "session_zero": (
            "The commander arrives at Area 1 with six contacts and three active "
            "threats already developing."
        ),
    }


def add_combat_module_setup(setup: dict) -> None:
    setup["player"]["data"]["equipment"]["weapons"] = [
        {
            "id": "weapon:gauss-rifle",
            "name": "Gauss Rifle",
            "damage": "2d8+2",
            "pen": 5,
            "rpm": 900,
            "magazine": 40,
        }
    ]
    setup["player"]["inventory"]["stackable"]["gauss-round"] = {
        "qty": 120,
        "weight": 0.02,
    }
    setup["nodes"].extend(
        [
            {
                "id": "weapon:gauss-rifle",
                "type": "weapon",
                "name": "Gauss Rifle",
                "data": {
                    "damage": "2d8+2",
                    "pen": 5,
                    "rpm": 900,
                    "magazine": 40,
                    "weapon_type": "assault_rifle",
                    "ammo_type": "gauss-round",
                    "source_module": "firearms-combat",
                },
            },
            {
                "id": "armor:combat-suit",
                "type": "armor",
                "name": "Combat Suit",
                "data": {
                    "ac_bonus": 4,
                    "prot": 5,
                    "source_module": "firearms-combat",
                },
            },
            {
                "id": "creature:raider",
                "type": "creature",
                "name": "Raider",
                "data": {
                    "hp": 20,
                    "ac": 13,
                    "prot": 2,
                    "attack": 4,
                    "damage": "1d8+2",
                    "source_module": "firearms-combat",
                },
            },
            {
                "id": "creature:marine-squad",
                "type": "creature",
                "name": "Marine",
                "data": {
                    "hp": 24,
                    "ac": 15,
                    "atk": 5,
                    "dmg": "2d8+2",
                    "source_module": "mass-combat",
                    "mass_combat_template": True,
                },
            },
            {
                "id": "creature:swarm-unit",
                "type": "creature",
                "name": "Swarm Unit",
                "data": {
                    "hp": 12,
                    "ac": 12,
                    "atk": 4,
                    "dmg": "1d8+1",
                    "source_module": "mass-combat",
                    "mass_combat_template": True,
                },
            },
        ]
    )
    setup["module_data"] = {
        "firearms-combat": {
            "enabled": True,
            "fire_modes": {
                "single": {"attacks": 1, "ammo": 1, "penalty": 0},
                "burst": {"duration_seconds": 1},
                "full_auto": {"duration_seconds": 3},
            },
            "penetration_vs_armor": {"pen_greater": "full damage"},
            "range_rules": {"normal": "+0"},
            "combat_style": {"style": "hybrid"},
            "combat_rules": {"cover": "Partial cover grants +2 AC."},
        },
        "mass-combat": {
            "enabled": True,
            "combat_rules": {"cover": "Groups can take cover."},
        },
    }


def test_load_creation_context_includes_core_and_only_selected_module():
    context = load_creation_context(
        ["mass-combat"],
        project_root=get_project_root(),
    )

    assert "CORE source: `.claude/commands/new-game.md`" in context
    assert "CORE source: `.claude/commands/create-character.md`" in context
    assert "### Module `mass-combat`" in context
    assert "### Module `firearms-combat`" not in context
    assert "Mass Combat — Creation Rules" in context
    assert "Backend-enforced creation contract" in context
    assert '"mass_combat_template": true' in context


def test_load_creation_context_rejects_unknown_module():
    with pytest.raises(CampaignSetupError, match="not installed"):
        load_creation_context(
            ["missing-module"],
            project_root=get_project_root(),
        )


def test_validate_campaign_setup_rejects_disconnected_world():
    setup = ready_setup()
    setup["edges"] = [
        edge
        for edge in setup["edges"]
        if edge.get("to") != "location:area-4"
    ]

    with pytest.raises(CampaignSetupError, match="Every location"):
        validate_campaign_setup(setup, [], project_root=get_project_root())


def test_ready_campaign_uses_stable_id_and_display_title(tmp_path):
    setup = ready_setup()
    campaigns = tmp_path / "world-state" / "campaigns"
    campaigns.mkdir(parents=True)

    with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
        result = create_campaign(
            name="starcraft-terran-command",
            display_name="StarCraft: Terran Command",
            genre="military-sci-fi",
            character={"name": "Steve", "class": "Commander"},
            setup=setup,
            require_ready=True,
        )

    assert result["success"] is True
    assert result["id"] == "starcraft-terran-command"
    assert result["display_name"] == "StarCraft: Terran Command"
    campaign_dir = campaigns / result["id"]
    world = json.loads((campaign_dir / "world.json").read_text(encoding="utf-8"))
    overview = json.loads(
        (campaign_dir / "campaign-overview.json").read_text(encoding="utf-8")
    )
    assert len(
        [
            node for node in world["nodes"].values()
            if node["type"] == "npc"
        ]
    ) == 6
    assert world["nodes"]["player:active"]["data"]["hp"]["max"] == 12
    assert overview["campaign_name"] == "StarCraft: Terran Command"
    assert overview["player_position"]["current_location"] == "Area 1"


def test_incomplete_ready_campaign_is_not_created(tmp_path):
    campaigns = tmp_path / "world-state" / "campaigns"
    campaigns.mkdir(parents=True)

    with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
        result = create_campaign(
            name="empty-shell",
            display_name="Empty Shell",
            character={"name": "Nobody"},
            setup={"nodes": []},
            require_ready=True,
        )

    assert result["success"] is False
    assert not (campaigns / "empty-shell").exists()


def test_wizard_event_uses_created_campaign_id(tmp_path):
    setup = ready_setup()
    campaigns = tmp_path / "world-state" / "campaigns"
    campaigns.mkdir(parents=True)
    events = WizardEvents()
    run_wizard_tool(
        events,
        "load_creation_rules",
        {"modules": [], "template_id": ""},
    )

    with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
        message = run_wizard_tool(
            events,
            "create_campaign",
            {
                "campaign_id": "safe-storage-id",
                "display_name": "Title: With Punctuation",
                "character_name": "Aria",
                "modules": [],
                "setup": deepcopy(setup),
            },
        )

    assert "created successfully" in message
    assert events.drain() == [
        {
            "type": "create_campaign",
            "campaign_id": "safe-storage-id",
            "display_name": "Title: With Punctuation",
            "success": True,
        }
    ]
    assert (campaigns / "safe-storage-id").exists()
    assert not (campaigns / "Title: With Punctuation").exists()


def test_wizard_cannot_create_before_loading_exact_rules(tmp_path):
    events = WizardEvents()
    message = run_wizard_tool(
        events,
        "create_campaign",
        {
            "campaign_id": "skipped-rules",
            "display_name": "Skipped Rules",
            "character_name": "Aria",
            "modules": [],
            "setup": ready_setup(),
        },
    )

    assert "rules must be loaded" in message
    assert events.drain()[0]["success"] is False
    assert not (tmp_path / "world-state" / "campaigns" / "skipped-rules").exists()


def test_selected_module_creation_contracts_are_persisted(tmp_path):
    project_root = get_project_root()
    setup = ready_setup()
    add_combat_module_setup(setup)
    for module_id in ("firearms-combat", "mass-combat"):
        shutil.copytree(
            project_root / "modules" / module_id,
            tmp_path / "modules" / module_id,
        )
    campaigns = tmp_path / "world-state" / "campaigns"
    campaigns.mkdir(parents=True)

    with patch("backend.campaign_api.get_project_root", return_value=tmp_path):
        result = create_campaign(
            name="combined-combat",
            display_name="Combined Combat",
            modules=["mass-combat", "firearms-combat"],
            character={"name": "Commander"},
            setup=setup,
            require_ready=True,
        )

    assert result["success"] is True
    campaign_dir = campaigns / "combined-combat"
    assert (
        campaign_dir / "module-data" / "firearms-combat.json"
    ).exists()
    assert (campaign_dir / "module-data" / "mass-combat.json").exists()
    world = json.loads((campaign_dir / "world.json").read_text(encoding="utf-8"))
    assert world["nodes"]["weapon:gauss-rifle"]["data"]["pen"] == 5
    assert world["nodes"]["creature:marine-squad"]["data"][
        "mass_combat_template"
    ] is True
