#!/usr/bin/env python3
"""
Tests for Firearms Combat Resolver
Uses isolated fake campaigns with tmp_path fixture
"""

import json
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from firearms_resolver import FirearmsCombatResolver, format_combat_output


@pytest.fixture
def fake_campaign(tmp_path):
    """Create a minimal fake campaign with firearms system"""
    world_state = tmp_path / "world-state"
    campaigns_dir = world_state / "campaigns"
    campaign_dir = campaigns_dir / "test-campaign"
    campaign_dir.mkdir(parents=True)

    active_campaign_file = world_state / "active-campaign.txt"
    active_campaign_file.write_text("test-campaign")

    character_data = {
        "name": "Test Stalker",
        "class": "Сталкер",
        "subclass": "Стрелок",
        "level": 5,
        "hp": {"current": 40, "max": 40},
        "abilities": {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "proficiency_bonus": 3,
        "xp": {"current": 1000, "next_level": 2000}
    }

    campaign_overview = {
        "name": "Test Campaign",
        "current_character": "Test Stalker",
        "current_location": "Test Zone",
        "current_time": "Day"
    }

    firearms_config = {
        "fire_modes": {
            "single": {
                "attacks": 1,
                "ammo": 1,
                "penalty": 0
            },
            "burst": {
                "attacks": 3,
                "ammo": 3,
                "penalty_per_shot": -3,
                "penalty_per_shot_sharpshooter": -2
            },
            "full_auto": {
                "penalty_per_shot": -3,
                "penalty_per_shot_sharpshooter": -2,
                "max_shots_per_target": 10
            }
        }
    }

    char_name = character_data.pop("name")
    world_json = {
        "nodes": {
            "player:active": {
                "type": "player",
                "name": char_name,
                "data": character_data
            },
            "weapon:ak-74": {
                "type": "weapon",
                "name": "AK-74",
                "data": {
                    "damage": "2d8+2",
                    "pen": 6,
                    "rpm": 650,
                    "ammo_type": "5.45x39mm",
                    "source_module": "firearms-combat"
                }
            }
        },
        "edges": []
    }
    character_data["name"] = char_name
    (campaign_dir / "campaign-overview.json").write_text(json.dumps(campaign_overview, indent=2))
    (campaign_dir / "world.json").write_text(json.dumps(world_json, indent=2))

    module_data_dir = campaign_dir / "module-data"
    module_data_dir.mkdir()
    (module_data_dir / "firearms-combat.json").write_text(json.dumps(firearms_config, indent=2))

    return world_state


def test_resolver_initialization(fake_campaign):
    """Test that resolver loads campaign correctly"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    assert resolver.character["name"] == "Test Stalker"
    assert resolver.character["subclass"] == "Стрелок"
    assert resolver._get_weapon_stats("AK-74")["damage"] == "2d8+2"


def test_attack_bonus_calculation(fake_campaign):
    """Test attack bonus calculation with sharpshooter subclass"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    attack_bonus = resolver._get_attack_bonus()
    dex_mod = (16 - 10) // 2
    prof_bonus = 3
    subclass_bonus = 2

    expected = dex_mod + prof_bonus + subclass_bonus
    assert attack_bonus == expected


def test_is_sharpshooter(fake_campaign):
    """Test sharpshooter detection"""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    assert resolver._is_sharpshooter() is True


def test_rpm_calculation(fake_campaign):
    """Test rounds-per-D&D-round calculation"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    ak74_rpm = 650
    rounds_per_6_seconds = resolver._calculate_rounds_per_dnd_round(ak74_rpm)

    expected = int((650 / 60) * 6)
    assert rounds_per_6_seconds == expected


def test_pen_vs_prot_scaling(fake_campaign):
    """Test penetration vs protection damage scaling"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    assert resolver._apply_pen_vs_prot(100, pen=10, prot=5) == 100
    assert resolver._apply_pen_vs_prot(100, pen=5, prot=12) == 25
    assert resolver._apply_pen_vs_prot(100, pen=6, prot=8) == 50


def test_full_auto_combat_basic(fake_campaign):
    """Test basic full-auto combat resolution"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [
        {"name": "Snork", "ac": 12, "hp": 15, "prot": 2}
    ]

    result = resolver.resolve_full_auto("AK-74", ammo_available=10, targets=targets)

    assert result["weapon"] == "AK-74"
    assert result["shots_fired"] == 10
    assert result["ammo_remaining"] == 0
    assert result["base_attack"] > 0
    assert result["is_sharpshooter"] is True
    assert len(result["targets"]) == 1


def test_full_auto_multi_target(fake_campaign):
    """Test full-auto combat with multiple targets"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [
        {"name": "Snork A", "ac": 12, "hp": 15, "prot": 2},
        {"name": "Snork B", "ac": 12, "hp": 15, "prot": 2},
        {"name": "Snork C", "ac": 12, "hp": 15, "prot": 2}
    ]

    result = resolver.resolve_full_auto("AK-74", ammo_available=30, targets=targets)

    assert result["shots_fired"] == 30
    assert len(result["targets"]) == 3

    total_shots = sum(t["shots"] for t in result["targets"])
    assert total_shots == 30


def test_combat_output_formatting(fake_campaign):
    """Test combat result output formatting"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [
        {"name": "Snork", "ac": 12, "hp": 15, "prot": 2}
    ]

    result = resolver.resolve_full_auto("AK-74", ammo_available=5, targets=targets)
    output = format_combat_output(result)

    assert "FIREARMS COMBAT RESOLVER" in output
    assert "AK-74" in output
    assert "Snork" in output
    assert "XP Gained:" in output


def test_character_update_after_combat(fake_campaign):
    """Test character XP update after combat"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    initial_xp = resolver.character["xp"]["current"]

    targets = [
        {"name": "Snork", "ac": 12, "hp": 1, "prot": 0}
    ]

    result = resolver.resolve_full_auto("AK-74", ammo_available=5, targets=targets)

    if result["enemies_killed"] > 0:
        resolver.update_character_after_combat(result)

        updated_char = resolver.player_mgr.get_player("Test Stalker")
        assert updated_char["xp"]["current"] > initial_xp


def test_single_fire_basic(fake_campaign):
    """Test single fire mode — one shot, one target"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 20, "prot": 2}]
    result = resolver.resolve_single("AK-74", ammo_available=30, targets=targets)

    assert result["fire_mode"] == "single"
    assert result["shots_fired"] == 1
    assert result["ammo_remaining"] == 29
    assert result["ammo_type"] == "5.45x39mm"
    assert len(result["targets"]) == 1
    assert result["targets"][0]["shots"] == 1
    assert len(result["targets"][0]["hits"]) == 1


def test_single_fire_no_ammo(fake_campaign):
    """Test single fire with 0 ammo"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 20, "prot": 2}]
    result = resolver.resolve_single("AK-74", ammo_available=0, targets=targets)

    assert result["shots_fired"] == 0
    assert result["ammo_remaining"] == 0


def test_burst_fire_basic(fake_campaign):
    """Test burst fire — 3 shots, progressive penalty"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 30, "prot": 2}]
    result = resolver.resolve_burst("AK-74", ammo_available=30, targets=targets)

    assert result["fire_mode"] == "burst"
    assert result["shots_fired"] == 3
    assert result["ammo_remaining"] == 27
    assert result["ammo_type"] == "5.45x39mm"
    assert len(result["targets"][0]["hits"]) == 3

    hits = result["targets"][0]["hits"]
    assert hits[0]["modifier"] >= hits[1]["modifier"]
    assert hits[1]["modifier"] >= hits[2]["modifier"]


def test_burst_fire_limited_ammo(fake_campaign):
    """Test burst fire with less than 3 ammo"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 20, "prot": 2}]
    result = resolver.resolve_burst("AK-74", ammo_available=2, targets=targets)

    assert result["shots_fired"] == 2
    assert result["ammo_remaining"] == 0


def test_full_auto_has_ammo_type(fake_campaign):
    """Test full_auto result includes ammo_type"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Snork", "ac": 12, "hp": 15, "prot": 2}]
    result = resolver.resolve_full_auto("AK-74", ammo_available=5, targets=targets)

    assert result["ammo_type"] == "5.45x39mm"
    assert result["fire_mode"] == "full_auto"


def test_missing_module_data_raises(tmp_path):
    """Test that missing module-data/firearms-combat.json raises RuntimeError"""
    world_state = tmp_path / "world-state"
    campaign_dir = world_state / "campaigns" / "no-config"
    campaign_dir.mkdir(parents=True)
    (world_state / "active-campaign.txt").write_text("no-config")

    character_data = {
        "name": "NoConfig",
        "class": "Воин",
        "level": 1,
        "hp": {"current": 10, "max": 10},
        "abilities": {"str": 10, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "proficiency_bonus": 2,
        "xp": {"current": 0, "next_level": 300}
    }

    overview = {"name": "No Config Test", "current_character": "NoConfig"}

    (campaign_dir / "character.json").write_text(json.dumps(character_data, indent=2))
    (campaign_dir / "campaign-overview.json").write_text(json.dumps(overview, indent=2))

    with pytest.raises(RuntimeError, match="No firearms config found"):
        FirearmsCombatResolver(str(world_state))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
