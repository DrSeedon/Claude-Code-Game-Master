"""Tests for lib/encounter_engine.py"""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from encounter_engine import check_encounter, _weighted_choice, _find_creature_by_type


@pytest.fixture
def campaign_dir(tmp_path):
    return tmp_path


@pytest.fixture
def base_overview():
    return {
        "campaign_name": "Test",
        "encounters": {
            "enabled": True,
            "chance_per_hour": 100,
            "min_hours_between": 0,
            "last_encounter_time": None,
            "types": {
                "bandits": 60,
                "beasts": 40,
            }
        }
    }


def write_overview(campaign_dir, data):
    f = campaign_dir / "campaign-overview.json"
    with open(f, "w") as fh:
        json.dump(data, fh)


def write_wiki(campaign_dir, data):
    f = campaign_dir / "wiki.json"
    with open(f, "w") as fh:
        json.dump(data, fh)


class TestNoConfig:
    def test_no_config_returns_none(self, campaign_dir):
        write_overview(campaign_dir, {"campaign_name": "Test"})
        result = check_encounter(3.0, campaign_dir)
        assert result is None

    def test_missing_overview_returns_none(self, campaign_dir):
        result = check_encounter(3.0, campaign_dir)
        assert result is None

    def test_zero_elapsed_returns_none(self, campaign_dir, base_overview):
        write_overview(campaign_dir, base_overview)
        result = check_encounter(0.0, campaign_dir)
        assert result is None

    def test_negative_elapsed_returns_none(self, campaign_dir, base_overview):
        write_overview(campaign_dir, base_overview)
        result = check_encounter(-1.0, campaign_dir)
        assert result is None


class TestDisabled:
    def test_disabled_returns_none(self, campaign_dir, base_overview):
        base_overview["encounters"]["enabled"] = False
        write_overview(campaign_dir, base_overview)
        result = check_encounter(5.0, campaign_dir)
        assert result is None


class TestMinHoursBetween:
    def test_respects_cooldown(self, campaign_dir, base_overview):
        base_overview["encounters"]["min_hours_between"] = 4
        base_overview["encounters"]["last_encounter_time"] = 1.0
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(2.0, campaign_dir)
        assert result is None

    def test_cooldown_expired_triggers(self, campaign_dir, base_overview):
        base_overview["encounters"]["min_hours_between"] = 2
        base_overview["encounters"]["last_encounter_time"] = 3.0
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["triggered"] is True

    def test_no_last_encounter_triggers(self, campaign_dir, base_overview):
        base_overview["encounters"]["last_encounter_time"] = None
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["triggered"] is True

    def test_state_persisted_after_no_encounter(self, campaign_dir, base_overview):
        base_overview["encounters"]["chance_per_hour"] = 0
        base_overview["encounters"]["min_hours_between"] = 2
        base_overview["encounters"]["last_encounter_time"] = None
        write_overview(campaign_dir, base_overview)
        check_encounter(3.0, campaign_dir)
        updated = json.loads((campaign_dir / "campaign-overview.json").read_text())
        assert updated["encounters"]["last_encounter_time"] is not None


class TestWeightedSelection:
    def test_single_type_always_selected(self):
        types = {"bandits": 100}
        category, weight = _weighted_choice(types)
        assert category == "bandits"
        assert weight == 100

    def test_empty_types_returns_unknown(self):
        category, weight = _weighted_choice({})
        assert category == "unknown"

    def test_distribution_roughly_correct(self):
        types = {"bandits": 60, "beasts": 40}
        counts = Counter()
        trials = 2000
        for _ in range(trials):
            cat, _ = _weighted_choice(types)
            counts[cat] += 1
        bandit_ratio = counts["bandits"] / trials
        assert 0.50 < bandit_ratio < 0.70, f"Expected ~60%, got {bandit_ratio:.2%}"

    def test_zero_weight_never_selected(self):
        types = {"bandits": 100, "ghosts": 0}
        for _ in range(50):
            cat, _ = _weighted_choice({"bandits": 100, "ghosts": 0})
            assert cat == "bandits"

    def test_result_type_in_campaign_check(self, campaign_dir, base_overview):
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["type"] in ("bandits", "beasts")
        assert result["total_weight"] == 100


class TestCreatureLookup:
    def test_finds_creature_by_tag(self, campaign_dir, base_overview):
        wiki = {
            "bandit": {
                "type": "creature",
                "name": "Bandit",
                "tags": ["bandits", "humanoid"],
                "mechanics": {"ac": 12, "hp": 11, "attack_bonus": 3, "damage": "1d6+1"}
            }
        }
        write_wiki(campaign_dir, wiki)
        write_overview(campaign_dir, base_overview)
        creature = _find_creature_by_type(wiki, "bandits")
        assert creature is not None
        assert creature["name"] == "Bandit"

    def test_finds_creature_by_singular_tag(self, campaign_dir):
        wiki = {
            "wolf": {
                "type": "creature",
                "name": "Wolf",
                "tags": ["beast"],
                "mechanics": {"ac": 13, "hp": 11}
            }
        }
        creature = _find_creature_by_type(wiki, "beasts")
        assert creature is not None
        assert creature["name"] == "Wolf"

    def test_finds_creature_by_name_match(self):
        wiki = {
            "zombie-common": {
                "type": "creature",
                "name": "Zombie",
                "tags": ["horror"],
                "mechanics": {"ac": 8, "hp": 22}
            }
        }
        creature = _find_creature_by_type(wiki, "undead")
        assert creature is None

    def test_ignores_non_creature_types(self):
        wiki = {
            "bandit-lore": {
                "type": "misc",
                "name": "Bandit Lore",
                "tags": ["bandits"]
            }
        }
        creature = _find_creature_by_type(wiki, "bandits")
        assert creature is None

    def test_creature_in_full_check_encounter(self, campaign_dir, base_overview):
        wiki = {
            "bandit": {
                "type": "creature",
                "name": "Bandit",
                "tags": ["bandits"],
                "mechanics": {"ac": 12, "hp": 11, "attack_bonus": 3, "damage": "1d6+1"}
            }
        }
        write_wiki(campaign_dir, wiki)
        base_overview["encounters"]["types"] = {"bandits": 100}
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["creature"] is not None
        assert result["creature"]["name"] == "Bandit"


class TestNoCreature:
    def test_returns_type_only_when_no_wiki(self, campaign_dir, base_overview):
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["triggered"] is True
        assert result["creature"] is None
        assert result["type"] in ("bandits", "beasts")

    def test_returns_type_only_when_no_matching_creature(self, campaign_dir, base_overview):
        wiki = {
            "wolf": {
                "type": "creature",
                "name": "Wolf",
                "tags": ["beast"],
                "mechanics": {"ac": 13, "hp": 11}
            }
        }
        write_wiki(campaign_dir, wiki)
        base_overview["encounters"]["types"] = {"patrol": 100}
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=1):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert result["creature"] is None
        assert result["type"] == "patrol"


class TestEncounterResult:
    def test_result_structure(self, campaign_dir, base_overview):
        write_overview(campaign_dir, base_overview)
        with patch("random.randint", return_value=5):
            result = check_encounter(1.0, campaign_dir)
        assert result is not None
        assert "triggered" in result
        assert "type" in result
        assert "weight" in result
        assert "total_weight" in result
        assert "hour" in result
        assert "roll" in result
        assert "chance" in result
        assert "creature" in result
        assert result["triggered"] is True
        assert result["hour"] == 1
        assert result["roll"] == 5
        assert result["chance"] == 100
