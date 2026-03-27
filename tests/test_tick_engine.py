"""Tests for WorldGraph tick/time engine methods."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
from world_graph import WorldGraph


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tick_graph(tmp_path):
    g = WorldGraph(tmp_path)

    g.add_node(
        "player:hero", "player", "Hero",
        data={
            "custom_stats": {
                "hp_stat": {"value": 50, "max": 100, "min": 0, "rate": -5}
            },
            "timed_effects": [],
            "money": 1000,
        }
    )

    g.add_node(
        "location:forge", "location", "The Forge",
        data={
            "production": [
                {
                    "worker": "npc:smith",
                    "item": "Swords",
                    "qty_dice": "1d4",
                    "skill_dc": 10,
                    "skill_bonus": 5,
                }
            ]
        }
    )

    g.add_node(
        "consequence:rent", "consequence", "Monthly Rent",
        data={
            "hours_elapsed": 0,
            "trigger_hours": 720,
        }
    )

    g.add_node(
        "misc:economy", "misc", "Economy",
        data={
            "expenses": [
                {"name": "food", "amount": 10, "interval_hours": 24}
            ],
            "income": []
        }
    )

    return g


# ---------------------------------------------------------------------------
# Custom Stats (8 tests)
# ---------------------------------------------------------------------------

class TestCustomStatDefine:
    def test_custom_stat_define(self, tick_graph):
        result = tick_graph.custom_stat_define(
            "dark_power", value=20, max=100, min=0, rate=-0.08, sleep_rate=0
        )
        assert result is True
        stat = tick_graph.custom_stat_get("dark_power")
        assert stat is not None
        assert stat["value"] == 20
        assert stat["max"] == 100
        assert stat["min"] == 0
        assert stat["rate"] == -0.08


class TestCustomStatGet:
    def test_custom_stat_get(self, tick_graph):
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat is not None
        assert stat["value"] == 50
        assert stat["max"] == 100
        assert stat["rate"] == -5


class TestCustomStatSetDelta:
    def test_custom_stat_set_delta(self, tick_graph):
        result = tick_graph.custom_stat_set("hp_stat", delta=10, reason="healed")
        assert result is True
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat["value"] == 60

    def test_custom_stat_set_delta_negative(self, tick_graph):
        result = tick_graph.custom_stat_set("hp_stat", delta=-20, reason="damage")
        assert result is True
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat["value"] == 30


class TestCustomStatSetAbsolute:
    def test_custom_stat_set_absolute(self, tick_graph):
        result = tick_graph.custom_stat_set("hp_stat", absolute=75, reason="reset")
        assert result is True
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat["value"] == 75


class TestCustomStatClampMax:
    def test_custom_stat_clamp_max(self, tick_graph):
        tick_graph.custom_stat_set("hp_stat", delta=999, reason="overflow")
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat["value"] == stat["max"]
        assert stat["value"] == 100


class TestCustomStatClampMin:
    def test_custom_stat_clamp_min(self, tick_graph):
        tick_graph.custom_stat_set("hp_stat", delta=-999, reason="underflow")
        stat = tick_graph.custom_stat_get("hp_stat")
        assert stat["value"] == stat["min"]
        assert stat["value"] == 0


class TestCustomStatList:
    def test_custom_stat_list(self, tick_graph):
        tick_graph.custom_stat_define("mana", value=30, max=50, min=0, rate=0)
        stats = tick_graph.custom_stat_list()
        assert isinstance(stats, list)
        names = [s["name"] for s in stats]
        assert "hp_stat" in names
        assert "mana" in names


class TestCustomStatMissing:
    def test_custom_stat_missing(self, tick_graph):
        result = tick_graph.custom_stat_get("nonexistent_stat")
        assert result is None


# ---------------------------------------------------------------------------
# Timed Effects (4 tests)
# ---------------------------------------------------------------------------

class TestTimedEffectAdd:
    def test_timed_effect_add(self, tick_graph):
        result = tick_graph.timed_effect_add(
            name="dark_blessing",
            stat="hp_stat",
            rate_mod=2.0,
            instant=0,
            hours=12,
        )
        assert result is True
        effects = tick_graph.timed_effect_list()
        assert any(e["name"] == "dark_blessing" for e in effects)


class TestTimedEffectList:
    def test_timed_effect_list(self, tick_graph):
        tick_graph.timed_effect_add("buff_a", "hp_stat", rate_mod=1.0, instant=0, hours=6)
        tick_graph.timed_effect_add("buff_b", "hp_stat", rate_mod=0.5, instant=0, hours=3)
        effects = tick_graph.timed_effect_list()
        assert isinstance(effects, list)
        assert len(effects) == 2
        names = [e["name"] for e in effects]
        assert "buff_a" in names
        assert "buff_b" in names


class TestTimedEffectExpires:
    def test_timed_effect_expires(self, tick_graph):
        tick_graph.timed_effect_add("short_buff", "hp_stat", rate_mod=1.0, instant=0, hours=2)
        tick_graph.tick(elapsed_hours=3)
        effects = tick_graph.timed_effect_list()
        assert not any(e["name"] == "short_buff" for e in effects)


class TestTimedEffectRateMod:
    def test_timed_effect_rate_mod(self, tick_graph):
        tick_graph.custom_stat_define("stamina", value=100, max=100, min=0, rate=-10, sleep_rate=0)
        tick_graph.timed_effect_add("slow_drain", "stamina", rate_mod=-5, instant=0, hours=24)

        tick_graph.tick(elapsed_hours=1)
        stat = tick_graph.custom_stat_get("stamina")

        assert stat["value"] < 100
        assert stat["value"] == pytest.approx(100 + (-10 + -5) * 1, abs=1)


# ---------------------------------------------------------------------------
# Tick Engine (8 tests)
# ---------------------------------------------------------------------------

class TestTickStatsDecay:
    def test_tick_stats_decay(self, tick_graph):
        initial = tick_graph.custom_stat_get("hp_stat")["value"]
        tick_graph.tick(elapsed_hours=2)
        stat = tick_graph.custom_stat_get("hp_stat")
        expected = max(0, initial + (-5) * 2)
        assert stat["value"] == pytest.approx(expected, abs=0.01)


class TestTickSleeping:
    def test_tick_sleeping(self, tick_graph):
        tick_graph.custom_stat_define(
            "energy", value=50, max=100, min=0, rate=-10, sleep_rate=5
        )
        tick_graph.tick(elapsed_hours=1, sleeping=True)
        stat = tick_graph.custom_stat_get("energy")
        assert stat["value"] == pytest.approx(55, abs=0.01)


class TestTickExpenses:
    def test_tick_expenses(self, tick_graph):
        player = tick_graph.get_node("player:hero")
        initial_money = player["data"]["money"]

        tick_graph.tick(elapsed_hours=24)

        player = tick_graph.get_node("player:hero")
        assert player["data"]["money"] < initial_money


class TestTickConsequences:
    def test_tick_consequences(self, tick_graph):
        before = tick_graph.get_node("consequence:rent")["data"]["hours_elapsed"]
        tick_graph.tick(elapsed_hours=10)
        after = tick_graph.get_node("consequence:rent")["data"]["hours_elapsed"]
        assert after == before + 10


class TestTickReturnsSummary:
    def test_tick_returns_summary(self, tick_graph):
        summary = tick_graph.tick(elapsed_hours=5)
        assert isinstance(summary, dict)
        assert "stat_changes" in summary
        assert "expired_effects" in summary
        assert "expenses_paid" in summary


class TestTickZeroHours:
    def test_tick_zero_hours(self, tick_graph):
        before = tick_graph.custom_stat_get("hp_stat")["value"]
        summary = tick_graph.tick(elapsed_hours=0)
        after = tick_graph.custom_stat_get("hp_stat")["value"]
        assert before == after
        assert summary["stat_changes"] == {}


class TestTickProduction:
    def test_tick_production(self, tick_graph):
        with patch("random.randint", return_value=3):
            summary = tick_graph.tick(elapsed_hours=8)

        assert "production" in summary
        forge_items = summary["production"].get("location:forge", [])
        assert any(p["item"] == "Swords" for p in forge_items)
        assert any(p["qty"] > 0 for p in forge_items)


class TestTickThresholdWarning:
    def test_tick_threshold_warning(self, tick_graph):
        tick_graph.custom_stat_define(
            "sanity", value=5, max=100, min=0, rate=-3,
            sleep_rate=0
        )
        summary = tick_graph.tick(elapsed_hours=2)

        assert "warnings" in summary
        sanity_warnings = [w for w in summary["warnings"] if "sanity" in w.get("stat", "")]
        assert len(sanity_warnings) > 0
