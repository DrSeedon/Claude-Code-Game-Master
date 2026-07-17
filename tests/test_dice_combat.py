"""Tests for auto-combat features in dice.py"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from dice import (
    DiceRoller,
    _load_creature,
    _load_spell,
    _resolve_attack,
    _resolve_spell_attack,
    main,
)


@pytest.fixture
def sample_char():
    return {
        "name": "Test Hero",
        "level": 5,
        "stats": {"str": 16, "dex": 14, "con": 12, "int": 18, "wis": 10, "cha": 8},
        "casting_stat": "int",
        "equipment": {
            "weapons": [
                {"name": "Longsword", "stat": "str", "proficient": True, "damage": "1d8+3", "bonus": 0, "equipped": True},
                {"name": "Shortbow", "stat": "dex", "proficient": True, "damage": "1d6+2", "bonus": 0, "equipped": False,
                 "ammo_type": "Arrows", "range_normal": 80, "range_long": 320},
                {"name": "Dagger", "stat": "dex", "proficient": True, "damage": "1d4+2", "bonus": 0, "equipped": False},
            ],
            "armor": {"base_ac": 14, "dex_bonus": True, "max_dex": 2}
        },
        "skills": {"perception": {"total": 3}},
        "saves": {"str": 6, "dex": 2},
    }


class TestResolveAttack:
    def test_equipped_weapon(self, sample_char):
        mod, name, damage, ammo, rn, rl = _resolve_attack(sample_char)
        assert name == "Longsword"
        assert damage == "1d8+3"
        assert mod == 3 + 3  # STR +3, prof +3
        assert ammo is None
        assert rn is None

    def test_named_weapon(self, sample_char):
        mod, name, damage, ammo, rn, rl = _resolve_attack(sample_char, "Shortbow")
        assert name == "Shortbow"
        assert damage == "1d6+2"
        assert ammo == "Arrows"
        assert rn == 80
        assert rl == 320

    def test_fuzzy_match(self, sample_char):
        mod, name, damage, ammo, rn, rl = _resolve_attack(sample_char, "short")
        assert name == "Shortbow"

    def test_dagger(self, sample_char):
        mod, name, damage, ammo, rn, rl = _resolve_attack(sample_char, "Dagger")
        assert name == "Dagger"
        assert mod == 2 + 3  # DEX +2, prof +3

    def test_no_weapons(self):
        char = {"name": "Unarmed", "level": 1, "stats": {"str": 10}, "equipment": {"weapons": []}, "skills": {}}
        mod, name, damage, ammo, rn, rl = _resolve_attack(char)
        assert ammo is None


class TestResolveSpellAttack:
    def test_int_caster(self, sample_char):
        mod, stat_mod, prof = _resolve_spell_attack(sample_char)
        assert stat_mod == 4  # INT 18
        assert prof == 3  # level 5
        assert mod == 7

    def test_wis_caster(self, sample_char):
        sample_char["casting_stat"] = "wis"
        mod, stat_mod, prof = _resolve_spell_attack(sample_char)
        assert stat_mod == 0  # WIS 10
        assert mod == 3

    def test_level_scaling(self):
        char = {"level": 1, "stats": {"int": 16}, "casting_stat": "int"}
        mod, _, prof = _resolve_spell_attack(char)
        assert prof == 2
        char["level"] = 9
        mod, _, prof = _resolve_spell_attack(char)
        assert prof == 4


class TestLoadCreature:
    def test_load_from_wiki(self, tmp_path):
        world = {"nodes": {"creature:goblin": {"type": "creature", "name": "Goblin", "data": {"hp": "7", "ac": "13", "attack_bonus": "4", "damage": "1d6+1"}}}}
        (tmp_path / "world.json").write_text(json.dumps(world))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_creature("goblin")
            assert result is not None
            assert result["id"] == "creature:goblin"
            assert result["name"] == "Goblin"
            assert result["mechanics"]["ac"] == "13"

    def test_fuzzy_match(self, tmp_path):
        world = {"nodes": {"creature:goblin-warrior": {"type": "creature", "name": "Goblin Warrior", "data": {"ac": "15"}}}}
        (tmp_path / "world.json").write_text(json.dumps(world))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_creature("goblin")
            assert result is not None
            assert result["name"] == "Goblin Warrior"

    def test_not_found(self, tmp_path):
        world = {"nodes": {"item:sword": {"type": "item", "name": "Sword", "data": {}}}}
        (tmp_path / "world.json").write_text(json.dumps(world))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            assert _load_creature("goblin") is None

    def test_no_wiki(self, tmp_path):
        with patch("dice._get_campaign_path", return_value=tmp_path):
            assert _load_creature("goblin") is None


class TestAutomaticDamage:
    def test_creature_attack_resolves_and_persists_in_one_call(
        self,
        tmp_path,
        monkeypatch,
        capsys,
    ):
        _write_world(
            tmp_path,
            {
                "player:active": {
                    "type": "player",
                    "name": "Steve",
                    "data": {
                        "hp": {"current": 12, "max": 12},
                        "ac": 15,
                        "prot": 6,
                        "stats": {"dex": 16},
                        "equipment": {"armor": {"ac": 15, "prot": 6}},
                    },
                },
                "creature:infested-miner": {
                    "type": "creature",
                    "name": "Infested Miner",
                    "data": {
                        "hp": 16,
                        "ac": 12,
                        "atk": 3,
                        "dmg": "1d6+1",
                        "pen": 1,
                        "prot": 1,
                    },
                },
            },
        )
        rolls = iter([13, 5])
        monkeypatch.setattr("dice.random.randint", lambda _a, _b: next(rolls))
        monkeypatch.setattr(
            sys,
            "argv",
            ["dice.py", "--defend", "--from", "infested-miner"],
        )

        with patch("dice._get_campaign_path", return_value=tmp_path):
            main()

        world = json.loads((tmp_path / "world.json").read_text())
        assert world["nodes"]["player:active"]["data"]["hp"]["current"] == 11
        output = capsys.readouterr().out
        assert "PEN 1 vs PROT 6 [QUARTER] -> 1 HP" in output
        assert "Steve: 12 -> 11 HP" in output

    def test_player_attack_persists_creature_hp(self, tmp_path, monkeypatch):
        _write_world(
            tmp_path,
            {
                "player:active": {
                    "type": "player",
                    "name": "Hero",
                    "data": {
                        "level": 1,
                        "stats": {"str": 16},
                        "equipment": {
                            "weapons": [{
                                "name": "Sword",
                                "stat": "str",
                                "proficient": True,
                                "equipped": True,
                                "damage": "1d6+3",
                                "pen": 2,
                            }],
                        },
                    },
                },
                "creature:guard": {
                    "type": "creature",
                    "name": "Guard",
                    "data": {"hp": 10, "ac": 10, "prot": 2},
                },
            },
        )
        rolls = iter([15, 5])
        monkeypatch.setattr("dice.random.randint", lambda _a, _b: next(rolls))
        monkeypatch.setattr(sys, "argv", ["dice.py", "--target", "guard"])

        with patch("dice._get_campaign_path", return_value=tmp_path):
            main()

        world = json.loads((tmp_path / "world.json").read_text())
        assert world["nodes"]["creature:guard"]["data"]["hp_current"] == 6

    def test_damage_spell_persists_creature_hp(self, tmp_path, monkeypatch):
        _write_world(
            tmp_path,
            {
                "player:active": {
                    "type": "player",
                    "name": "Mage",
                    "data": {
                        "level": 1,
                        "stats": {"int": 16},
                        "casting_stat": "int",
                    },
                },
                "spell:plasma-bolt": {
                    "type": "spell",
                    "name": "Plasma Bolt",
                    "data": {
                        "damage": "1d6",
                        "attack_type": "ranged",
                        "pen": 3,
                    },
                },
                "creature:drone": {
                    "type": "creature",
                    "name": "Drone",
                    "data": {"hp": 10, "ac": 10, "prot": 1},
                },
            },
        )
        rolls = iter([15, 4])
        monkeypatch.setattr("dice.random.randint", lambda _a, _b: next(rolls))
        monkeypatch.setattr(
            sys,
            "argv",
            ["dice.py", "--spell", "plasma-bolt", "--target", "drone"],
        )

        with patch("dice._get_campaign_path", return_value=tmp_path):
            main()

        world = json.loads((tmp_path / "world.json").read_text())
        assert world["nodes"]["creature:drone"]["data"]["hp_current"] == 6


def _write_world(tmp_path, nodes):
    world = {"nodes": nodes, "edges": []}
    (tmp_path / "world.json").write_text(json.dumps(world))


class TestLoadSpell:
    def test_load_spell(self, tmp_path):
        _write_world(tmp_path, {"spell:fire-bolt": {"type": "spell", "name": "Fire Bolt", "data": {"mechanics": {"damage": "1d10", "attack_type": "ranged"}}}})
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("fire-bolt")
            assert result is not None
            assert result["mechanics"]["damage"] == "1d10"

    def test_load_ability(self, tmp_path):
        _write_world(tmp_path, {"ability:shyish-bolt": {"type": "ability", "name": "Shyish Bolt", "data": {"mechanics": {"damage": "2d6", "save_type": "DEX"}}}})
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("shyish")
            assert result is not None

    def test_technique_type(self, tmp_path):
        _write_world(tmp_path, {"technique:hand-of-dust": {"type": "technique", "name": "Hand of Dust", "data": {"mechanics": {}}}})
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("hand-of-dust")
            assert result is not None

    def test_weapon_not_spell(self, tmp_path):
        _write_world(tmp_path, {"weapon:longsword": {"type": "weapon", "name": "Longsword", "data": {}}})
        with patch("dice._get_campaign_path", return_value=tmp_path):
            assert _load_spell("longsword") is None


class TestDiceRoller:
    def test_basic_roll(self):
        roller = DiceRoller()
        result = roller.roll("1d20")
        assert 1 <= result["total"] <= 20

    def test_modifier(self):
        roller = DiceRoller()
        result = roller.roll("1d20+5")
        assert result["modifier"] == 5

    def test_advantage(self):
        roller = DiceRoller()
        result = roller.roll("2d20kh1")
        assert result["type"] == "advantage"
        assert len(result["kept"]) == 1
        assert len(result["discarded"]) == 1

    def test_disadvantage(self):
        roller = DiceRoller()
        result = roller.roll("2d20kl1")
        assert result["type"] == "disadvantage"
