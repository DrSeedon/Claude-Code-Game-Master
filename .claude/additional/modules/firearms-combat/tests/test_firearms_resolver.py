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
                "duration_seconds": 1,
                "max_salvos_per_target": 3,
                "max_salvos_total": 3,
                "penalty_per_salvo": -2,
                "penalty_per_salvo_sharpshooter": -1,
                "max_hits_per_salvo": 3,
                "hit_margin_per_extra_bullet": 5
            },
            "full_auto": {
                "duration_seconds": 3,
                "max_salvos_per_target": 6,
                "max_salvos_total": 12,
                "penalty_per_salvo": -2,
                "penalty_per_salvo_sharpshooter": -1,
                "max_hits_per_salvo": 3,
                "hit_margin_per_extra_bullet": 5
            }
        }
    }

    char_name = character_data.pop("name")
    world_json = {
        "nodes": {
            "player:active": {
                "type": "player",
                "name": char_name,
                "data": character_data,
                "inventory": {
                    "stackable": {
                        "5.45x39mm": {"qty": 100, "weight": 0.02},
                        "8mm spike": {"qty": 500, "weight": 0.02}
                    },
                    "unique": []
                }
            },
            "weapon:ak-74": {
                "type": "weapon",
                "name": "AK-74",
                "data": {
                    "damage": "2d8+2",
                    "pen": 6,
                    "rpm": 650,
                    "magazine": 30,
                    "allowed_fire_modes": ["single", "burst", "full_auto"],
                    "ammo_type": "5.45x39mm",
                    "source_module": "firearms-combat"
                }
            },
            "weapon:c-14-impaler": {
                "type": "weapon",
                "name": "C-14 Impaler",
                "data": {
                    "damage": "2d8+3",
                    "pen": 5,
                    "rpm": 1800,
                    "magazine": 500,
                    "allowed_fire_modes": ["single", "burst", "full_auto"],
                    "ammo_type": "8mm spike",
                    "source_module": "firearms-combat"
                }
            }
        },
        "edges": []
    }
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
    """Test rounds fired for a configured trigger duration."""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    assert resolver._calculate_rounds_for_duration(650, 1) == 10
    assert resolver._calculate_rounds_for_duration(650, 3) == 32
    assert resolver._calculate_rounds_for_duration(1800, 1) == 30
    assert resolver._calculate_rounds_for_duration(1800, 3) == 90


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
    assert result["magazine_remaining"] == 0
    assert result["reload_required"] is True
    assert result["duration_seconds"] == 3
    assert result["salvos_fired"] == 6
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

    total_shots = sum(t["rounds_allocated"] for t in result["targets"])
    assert total_shots == 30
    assert result["salvos_fired"] <= 12


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
    """Combat persistence updates XP and ammunition in WorldGraph."""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    initial_xp = resolver.character["xp"]["current"]
    resolver.update_character_after_combat({
        "total_xp": 25,
        "ammo_type": "5.45x39mm",
        "shots_fired": 5,
    })

    player = resolver.world_graph.get_node("player:active")
    assert player["data"]["xp"]["current"] == initial_xp + 25
    assert player["inventory"]["stackable"]["5.45x39mm"]["qty"] == 95


def test_combat_persistence_rolls_back_xp_when_ammo_fails(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    before = resolver.world_graph.get_node("player:active")

    with pytest.raises(RuntimeError, match="ammunition"):
        resolver.update_character_after_combat({
            "total_xp": 25,
            "ammo_type": "missing-ammo",
            "shots_fired": 5,
        })

    after = resolver.world_graph.get_node("player:active")
    assert after["data"]["xp"] == before["data"]["xp"]
    assert after["inventory"] == before["inventory"]


def test_ammo_deduction_uses_world_graph_inventory(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))

    assert resolver._deduct_ammo("5.45x39mm", 7) is True

    player = resolver.world_graph.get_node("player:active")
    assert player["inventory"]["stackable"]["5.45x39mm"]["qty"] == 93


def test_combat_xp_preserves_level_up_behavior(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.world_graph.update_node("player:active", {
        "data": {"level": 1, "xp": {"current": 275, "next_level": 300}}
    })

    resolver.update_character_after_combat({"total_xp": 50, "shots_fired": 0})

    player = resolver.world_graph.get_node("player:active")
    assert player["data"]["level"] == 2
    assert player["data"]["xp"] == {"current": 325, "next_level": 900}


def test_combat_xp_can_cross_multiple_levels(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.world_graph.update_node(
        "player:active", {"data": {"level": 1, "xp": {"current": 0, "next_level": 300}}}
    )

    result = resolver.progression.award_xp(3000)

    player = resolver.world_graph.get_node("player:active")
    assert result["new_level"] == 4
    assert player["data"]["xp"] == {"current": 3000, "next_level": 6500}


def test_combat_xp_normalizes_integer_storage(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.world_graph.update_node(
        "player:active", {"data": {"level": 2, "xp": 500}}
    )

    resolver.progression.award_xp(50)

    player = resolver.world_graph.get_node("player:active")
    assert player["data"]["xp"] == {"current": 550, "next_level": 900}


def test_combat_xp_keeps_level_twenty_capped(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.world_graph.update_node(
        "player:active", {"data": {"level": 20, "xp": 355000}}
    )

    result = resolver.progression.award_xp(25)

    player = resolver.world_graph.get_node("player:active")
    assert result["next_level_xp"] == "MAX"
    assert player["data"]["level"] == 20
    assert player["data"]["xp"] == {"current": 355025, "next_level": 355025}


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
    """A one-second burst spends RPM-based ammo but uses three salvos."""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 30, "prot": 2}]
    result = resolver.resolve_burst("AK-74", ammo_available=30, targets=targets)

    assert result["fire_mode"] == "burst"
    assert result["shots_fired"] == 10
    assert result["ammo_remaining"] == 20
    assert result["ammo_type"] == "5.45x39mm"
    assert len(result["targets"][0]["hits"]) == 3
    assert result["targets"][0]["rounds_allocated"] == 10
    assert sum(hit["rounds_in_salvo"] for hit in result["targets"][0]["hits"]) == 10

    hits = result["targets"][0]["hits"]
    assert hits[0]["modifier"] >= hits[1]["modifier"]
    assert hits[1]["modifier"] >= hits[2]["modifier"]


def test_burst_fire_limited_ammo(fake_campaign):
    """Burst consumes only the rounds currently available."""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Bandit", "ac": 12, "hp": 20, "prot": 2}]
    result = resolver.resolve_burst("AK-74", ammo_available=2, targets=targets)

    assert result["shots_fired"] == 2
    assert result["ammo_remaining"] == 0
    assert result["salvos_fired"] == 2


def test_starcraft_rpm_consumption(fake_campaign):
    """High-RPM weapons spend physical rounds without creating one roll per bullet."""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    target = [{"name": "Hydralisk", "ac": 14, "hp": 200, "prot": 4}]

    burst = resolver.resolve_burst("C-14 Impaler", ammo_available=500, targets=target)
    assert burst["shots_fired"] == 30
    assert burst["ammo_remaining"] == 470
    assert burst["salvos_fired"] == 3

    target[0]["hp"] = 200
    full_auto = resolver.resolve_full_auto("C-14 Impaler", ammo_available=500, targets=target)
    assert full_auto["shots_fired"] == 90
    assert full_auto["ammo_remaining"] == 410
    assert full_auto["salvos_fired"] == 6


def test_magazine_caps_rounds_fired(fake_campaign):
    """A fire action cannot consume more than the weapon's loaded magazine."""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.firearms_config["fire_modes"]["full_auto"]["duration_seconds"] = 6
    target = [{"name": "Target", "ac": 30, "hp": 200, "prot": 0}]

    result = resolver.resolve_full_auto("AK-74", ammo_available=100, targets=target)

    assert result["shots_fired"] == 30
    assert result["ammo_remaining"] == 70
    assert result["magazine_remaining"] == 0
    assert result["reload_required"] is True


def test_margin_controls_bullets_hit(fake_campaign, monkeypatch):
    """A successful salvo lands more bullets only when it beats AC by 5 or 10."""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    rolls = iter([15, 10, 1])
    monkeypatch.setattr(resolver, "_roll_d20", lambda: next(rolls))
    monkeypatch.setattr(resolver, "_roll_damage", lambda _: 10)
    target = [{"name": "Target", "ac": 13, "hp": 100, "prot": 2}]

    result = resolver.resolve_burst("AK-74", ammo_available=30, targets=target)

    salvos = result["targets"][0]["hits"]
    assert [salvo["bullets_hit"] for salvo in salvos] == [3, 1, 0]
    assert result["bullets_hit"] == 4
    assert result["total_damage"] == 40


def test_automatic_nat20_crits_only_first_bullet(fake_campaign, monkeypatch):
    """A natural 20 does not turn every bullet in the salvo into a critical hit."""
    resolver = FirearmsCombatResolver(str(fake_campaign))
    mode = resolver.firearms_config["fire_modes"]["burst"]
    mode["max_salvos_per_target"] = 1
    mode["max_salvos_total"] = 1
    monkeypatch.setattr(resolver, "_roll_d20", lambda: 20)
    monkeypatch.setattr(
        resolver,
        "_roll_damage",
        lambda dice: 20 if dice.startswith("4d") else 10,
    )
    target = [{"name": "Target", "ac": 30, "hp": 100, "prot": 2}]

    result = resolver.resolve_burst("AK-74", ammo_available=30, targets=target)

    salvo = result["targets"][0]["hits"][0]
    assert salvo["bullets_hit"] == 2
    assert salvo["crit_bullets"] == 1
    assert salvo["bullet_damage"][0]["critical"] is True
    assert salvo["bullet_damage"][1]["critical"] is False
    assert result["total_damage"] == 30


def test_full_auto_has_ammo_type(fake_campaign):
    """Test full_auto result includes ammo_type"""
    resolver = FirearmsCombatResolver(str(fake_campaign))

    targets = [{"name": "Snork", "ac": 12, "hp": 15, "prot": 2}]
    result = resolver.resolve_full_auto("AK-74", ammo_available=5, targets=targets)

    assert result["ammo_type"] == "5.45x39mm"
    assert result["fire_mode"] == "full_auto"


def test_weapon_rejects_unsupported_fire_mode(fake_campaign):
    resolver = FirearmsCombatResolver(str(fake_campaign))
    resolver.world_graph.update_node(
        "weapon:c-14-impaler",
        {"data": {"allowed_fire_modes": ["single"]}},
    )
    target = [{"name": "Target", "ac": 10, "hp": 10, "prot": 0}]

    with pytest.raises(ValueError, match="not available"):
        resolver.resolve_full_auto("C-14 Impaler", 500, target)


def test_missing_module_data_raises(tmp_path):
    """Test that missing module-data/firearms-combat.json raises RuntimeError"""
    world_state = tmp_path / "world-state"
    campaign_dir = world_state / "campaigns" / "no-config"
    campaign_dir.mkdir(parents=True)
    (world_state / "active-campaign.txt").write_text("no-config")

    overview = {"name": "No Config Test", "current_character": "NoConfig"}
    (campaign_dir / "campaign-overview.json").write_text(json.dumps(overview, indent=2))
    (campaign_dir / "world.json").write_text(json.dumps({
        "nodes": {
            "player:active": {
                "type": "player",
                "name": "NoConfig",
                "data": {"level": 1, "xp": {"current": 0, "next_level": 300}}
            }
        },
        "edges": []
    }, indent=2))

    with pytest.raises(RuntimeError, match="No firearms config found"):
        FirearmsCombatResolver(str(world_state))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
