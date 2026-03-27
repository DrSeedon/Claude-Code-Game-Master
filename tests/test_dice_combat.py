"""Tests for auto-combat features in dice.py"""
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from dice import DiceRoller, _resolve_attack, _resolve_spell_attack, _load_creature, _load_spell


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
        wiki = {"goblin": {"type": "creature", "name": "Goblin", "mechanics": {"hp": "7", "ac": "13", "attack_bonus": "4", "damage": "1d6+1"}}}
        wiki_file = tmp_path / "wiki.json"
        wiki_file.write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_creature("goblin")
            assert result is not None
            assert result["name"] == "Goblin"
            assert result["mechanics"]["ac"] == "13"

    def test_fuzzy_match(self, tmp_path):
        wiki = {"goblin-warrior": {"type": "creature", "name": "Goblin Warrior", "mechanics": {"ac": "15"}}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_creature("goblin")
            assert result is not None
            assert result["name"] == "Goblin Warrior"

    def test_not_found(self, tmp_path):
        wiki = {"sword": {"type": "weapon", "name": "Sword"}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            assert _load_creature("goblin") is None

    def test_no_wiki(self, tmp_path):
        with patch("dice._get_campaign_path", return_value=tmp_path):
            assert _load_creature("goblin") is None


class TestLoadSpell:
    def test_load_spell(self, tmp_path):
        wiki = {"fire-bolt": {"type": "spell", "name": "Fire Bolt", "mechanics": {"damage": "1d10", "attack_type": "ranged"}}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("fire-bolt")
            assert result is not None
            assert result["mechanics"]["damage"] == "1d10"

    def test_load_ability(self, tmp_path):
        wiki = {"shyish-bolt": {"type": "ability", "name": "Shyish Bolt", "mechanics": {"damage": "2d6", "save_type": "DEX"}}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("shyish")
            assert result is not None

    def test_technique_type(self, tmp_path):
        wiki = {"hand-of-dust": {"type": "technique", "name": "Hand of Dust", "mechanics": {}}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
        with patch("dice._get_campaign_path", return_value=tmp_path):
            result = _load_spell("hand-of-dust")
            assert result is not None

    def test_weapon_not_spell(self, tmp_path):
        wiki = {"longsword": {"type": "weapon", "name": "Longsword"}}
        (tmp_path / "wiki.json").write_text(json.dumps(wiki))
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
