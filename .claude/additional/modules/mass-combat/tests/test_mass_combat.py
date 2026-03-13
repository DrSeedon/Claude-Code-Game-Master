#!/usr/bin/env python3
"""Tests for Mass Combat Engine."""

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def strip_ansi(s):
    return re.sub(r'\033\[[0-9;]*m', '', s)

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "modules" / "mass-combat" / "lib"))

from mass_combat_engine import MassCombatEngine


@pytest.fixture
def engine(tmp_path):
    campaign_dir = tmp_path / "world-state" / "campaigns" / "test"
    campaign_dir.mkdir(parents=True)
    active = tmp_path / "world-state" / "active-campaign.txt"
    active.write_text("test")

    with patch.object(MassCombatEngine, "__init__", lambda self, *a, **kw: None):
        e = MassCombatEngine.__new__(MassCombatEngine)
        e.campaign_dir = campaign_dir
        module_data_dir = campaign_dir / "module-data"
        module_data_dir.mkdir(parents=True, exist_ok=True)
        e.state_path = module_data_dir / "combat-state.json"
        e.state = {}
        e.test_mode = False
        e.templates = {}
    return e


class TestInit:
    def test_init_creates_battle(self, engine):
        result = engine.init_battle("Test")
        assert "initialized" in result
        assert engine.state["active"] is True
        assert engine.state["name"] == "Test"

    def test_init_blocks_if_active(self, engine):
        engine.init_battle("First")
        result = engine.init_battle("Second")
        assert "ERROR" in result


class TestAddUnits:
    def test_add_template(self, engine):
        engine.init_battle("Test")
        result = engine.add_units("enemies", "droids", "B1", 4, 13, 7, 3, "1d6")
        assert "4 B1 added" in strip_ansi(result)
        assert len(engine.state["units"]) == 4
        assert "B1-01" in engine.state["units"]
        assert "B1-04" in engine.state["units"]

    def test_add_named(self, engine):
        engine.init_battle("Test")
        result = engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        assert "Хантер" in engine.state["units"]
        assert engine.state["units"]["Хантер"]["hp"] == 17

    def test_groups_tracked(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "bridge", "B1", 3, 13, 7, 3, "1d6")
        engine.add_units("enemies", "patrol", "B1", 2, 13, 7, 3, "1d6")
        assert "bridge" in engine.state["groups"]
        assert "patrol" in engine.state["groups"]
        assert len(engine.state["groups"]["bridge"]["unit_ids"]) == 3
        assert len(engine.state["groups"]["patrol"]["unit_ids"]) == 2


class TestRoundAttack:
    def test_round_rolls_for_each(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.round_attack("droids", target_group="heroes")
        assert "B1-01" in result
        assert "B1-02" in result
        assert "B1-03" in result
        assert "Хантер" in result

    def test_round_count_limits(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 6, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.round_attack("droids", target_group="heroes", count=2)
        lines = [l for l in result.split("\n") if l.startswith("🎲")]
        assert len(lines) == 2

    def test_no_target_group_error(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.round_attack("droids")
        assert "ERROR" in result


class TestSingleAttack:
    def test_attack_specific_targets(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.single_attack("Хантер", ["B1-01"])
        assert "Хантер → B1-01" in strip_ansi(result)

    def test_attack_dead_target_skipped(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 2, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        engine.kill_unit("B1-01")
        result = engine.single_attack("Хантер", ["B1-01", "B1-02"])
        assert "already dead" in result


class TestAOE:
    def test_aoe_hits_all(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        result = engine.aoe_damage("Grenade", ["B1-01", "B1-02", "B1-03"], "2d6")
        assert "B1-01" in result
        assert "B1-02" in result
        assert "B1-03" in result

    def test_aoe_with_save(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 1, 13, 100, 3, "1d6")
        result = engine.aoe_damage("Grenade", ["B1-01"], "2d6", save_type="DEX", save_dc=10)
        assert "save" in result


class TestCover:
    def test_cover_adds_ac(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        engine.set_cover("heroes", True)

        assert engine.state["units"]["Хантер"]["cover"] is True
        assert engine.state["groups"]["heroes"]["cover"] is True

    def test_cover_remove(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        engine.set_cover("heroes", True)
        engine.set_cover("heroes", False)
        assert engine.state["units"]["Хантер"]["cover"] is False


class TestDamageHealKill:
    def test_direct_damage(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.direct_damage("Хантер", 5)
        assert "HP 17→12" in strip_ansi(result)

    def test_kill_on_damage(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 5, 6, "2d6")
        result = engine.direct_damage("Хантер", 10)
        assert "KILLED" in result
        assert not engine.state["units"]["Хантер"]["alive"]

    def test_heal(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        engine.direct_damage("Хантер", 10)
        result = engine.heal("Хантер", 5)
        assert "12" in result

    def test_heal_caps_at_max(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        engine.direct_damage("Хантер", 2)
        engine.heal("Хантер", 100)
        assert engine.state["units"]["Хантер"]["hp"] == 17

    def test_kill(self, engine):
        engine.init_battle("Test")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = engine.kill_unit("Хантер")
        assert "killed" in result
        assert engine.state["units"]["Хантер"]["hp"] == 0


class TestStatus:
    def test_status_shows_all(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.add_named("allies", "heroes", "Хантер", 14, 17, 6, "2d6")
        result = strip_ansi(engine.status())
        assert "enemies" in result
        assert "allies" in result
        assert "B1-01" in result
        assert "Хантер" in result


class TestEndBattle:
    def test_end_calculates_xp(self, engine):
        engine.init_battle("Test")
        engine.add_units("enemies", "droids", "B1", 3, 13, 7, 3, "1d6")
        engine.kill_unit("B1-01")
        engine.kill_unit("B1-02")
        result = engine.end_battle()
        assert "50" in result
        assert "2 enemies killed" in result

    def test_end_cleans_state(self, engine):
        engine.init_battle("Test")
        engine.end_battle()
        assert not engine.state_path.exists()
