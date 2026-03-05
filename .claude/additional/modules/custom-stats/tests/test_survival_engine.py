#!/usr/bin/env python3
"""Tests for survival_engine.py — isolated with tmp campaign directories."""

import json
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.json_ops import JsonOperations


# ─── Fixtures ──────────────────────────────────────────────

def make_campaign(tmp_path, campaign_overview, character):
    """Create a fake campaign structure in tmp_path."""
    ws = tmp_path / "world-state"
    campaigns = ws / "campaigns" / "test-campaign"
    campaigns.mkdir(parents=True)

    (ws / "active-campaign.txt").write_text("test-campaign")

    ops = JsonOperations(str(campaigns))
    ops.save_json("campaign-overview.json", campaign_overview)
    ops.save_json("character.json", character)
    ops.save_json("consequences.json", {"active": [], "resolved": []})

    return ws


def base_campaign(rules_override=None):
    """Standard campaign overview with time effects enabled."""
    rules = {
        "time_effects": {
            "enabled": True,
            "rules": [
                {"stat": "hunger", "per_hour": -2},
                {"stat": "thirst", "per_hour": -3},
                {"stat": "radiation", "per_hour": 1}
            ],
            "stat_consequences": {}
        }
    }
    if rules_override:
        rules["time_effects"].update(rules_override)

    return {
        "campaign_name": "Test Campaign",
        "current_character": "TestHero",
        "time_of_day": "Day",
        "current_date": "Day 1",
        "precise_time": "12:00",
        "campaign_rules": rules
    }


def base_character():
    return {
        "name": "TestHero",
        "level": 5,
        "hp": {"current": 30, "max": 40},
        "abilities": {"strength": 14, "dexterity": 12, "constitution": 16,
                      "intelligence": 10, "wisdom": 13, "charisma": 8},
        "custom_stats": {
            "hunger": {"current": 80, "min": 0, "max": 100},
            "thirst": {"current": 70, "min": 0, "max": 100},
            "radiation": {"current": 10, "min": 0, "max": 500}
        }
    }


def load_engine(ws_path):
    """Import and instantiate SurvivalEngine pointing at our tmp world-state."""
    from importlib import import_module, reload
    mod = import_module('.claude.modules.survival-stats.lib.survival_engine'.replace('-', '_').replace('.', '_'))
    # Can't import via dotted path with hyphens — just import directly
    # Instead, use the class directly
    pass

# Since survival_engine uses CampaignManager("world-state") by default,
# we need to construct it manually for tests.

def make_engine(ws_path):
    """Build a SurvivalEngine-like object pointing at tmp campaign."""
    from lib.player_manager import PlayerManager
    from lib.campaign_manager import CampaignManager

    class TestSurvivalEngine:
        def __init__(self, ws):
            self.campaign_mgr = CampaignManager(str(ws))
            self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()
            self.json_ops = JsonOperations(str(self.campaign_dir))
            self.player_mgr = PlayerManager(str(ws))

    # Import the real class methods
    sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "modules" / "custom-stats" / "lib"))
    from survival_engine import SurvivalEngine

    engine = TestSurvivalEngine(ws_path)
    engine.__class__ = type('TestEngine', (TestSurvivalEngine,), {
        'tick': SurvivalEngine.tick,
        'status': SurvivalEngine.status,
        '_normalize_custom_stats': SurvivalEngine._normalize_custom_stats,
        '_apply_time_effects': SurvivalEngine._apply_time_effects,
        '_is_blocked': SurvivalEngine._is_blocked,
        '_check_rule_condition': SurvivalEngine._check_rule_condition,
        '_check_stat_consequences': SurvivalEngine._check_stat_consequences,
        '_print_report': SurvivalEngine._print_report,
        'set_rate_modifier': SurvivalEngine.set_rate_modifier,
        'show_rates': SurvivalEngine.show_rates,
        '_get_active_character_name': SurvivalEngine._get_active_character_name,
        'add_effect': SurvivalEngine.add_effect,
        'remove_effect': SurvivalEngine.remove_effect,
        'list_effects': SurvivalEngine.list_effects,
    })

    return engine


# ─── Tests: _check_rule_condition ──────────────────────────

class TestCheckRuleCondition:
    def setup_method(self):
        self.char = base_character()

    def _check(self, condition):
        sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "modules" / "custom-stats" / "lib"))
        from survival_engine import SurvivalEngine
        return SurvivalEngine._check_rule_condition(None, condition, self.char)

    def test_hp_less_than_max(self):
        assert self._check("hp < max") is True

    def test_hp_at_max(self):
        self.char['hp']['current'] = 40
        assert self._check("hp < max") is False

    def test_hp_greater_than_zero(self):
        assert self._check("hp > 0") is True

    def test_hp_at_zero(self):
        self.char['hp']['current'] = 0
        assert self._check("hp > 0") is False

    def test_stat_less_than_value(self):
        assert self._check("stat:hunger < 90") is True

    def test_stat_greater_equal(self):
        self.char['custom_stats']['radiation']['current'] = 150
        assert self._check("stat:radiation >= 100") is True

    def test_stat_equal(self):
        self.char['custom_stats']['hunger']['current'] = 0
        assert self._check("stat:hunger == 0") is True

    def test_stat_not_equal(self):
        assert self._check("stat:hunger != 0") is True

    def test_unknown_stat_returns_true(self):
        assert self._check("stat:nonexistent < 50") is True

    def test_malformed_condition_returns_true(self):
        assert self._check("garbage") is True

    def test_empty_condition(self):
        assert self._check("") is True


# ─── Tests: Time Effects (tick) ────────────────────────────

class TestTimeEffects:
    def test_basic_tick_decreases_stats(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(2)

        assert len(result['stat_changes']) > 0

        hunger_change = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger_change is not None
        assert hunger_change['change'] < 0

        thirst_change = next((c for c in result['stat_changes'] if c['stat'] == 'thirst'), None)
        assert thirst_change is not None
        assert thirst_change['change'] < 0

    def test_radiation_increases(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(3)

        rad_change = next((c for c in result['stat_changes'] if c['stat'] == 'radiation'), None)
        assert rad_change is not None
        assert rad_change['change'] > 0

    def test_stat_clamped_to_min(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['current'] = 2
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        result = engine.tick(5)

        hunger_change = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger_change is not None
        assert hunger_change['new'] >= 0

    def test_stat_clamped_to_max(self, tmp_path):
        char = base_character()
        char['custom_stats']['radiation']['current'] = 498
        ws = make_campaign(
            tmp_path,
            base_campaign({"rules": [{"stat": "radiation", "per_hour": 5}]}),
            char
        )
        engine = make_engine(ws)

        result = engine.tick(3)

        rad_change = next((c for c in result['stat_changes'] if c['stat'] == 'radiation'), None)
        assert rad_change is not None
        assert rad_change['new'] <= 500

    def test_zero_elapsed_no_changes(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(0)

        assert result['stat_changes'] == []

    def test_fractional_hours_truncated(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(0.5)

        assert result['stat_changes'] == []

    def test_disabled_time_effects_skip(self, tmp_path):
        campaign = base_campaign()
        campaign['campaign_rules']['time_effects']['enabled'] = False
        ws = make_campaign(tmp_path, campaign, base_character())
        engine = make_engine(ws)

        result = engine.tick(5)

        assert result['stat_changes'] == []


# ─── Tests: Sleep Mode ─────────────────────────────────────

class TestSleepMode:
    def test_sleep_restores_stat(self, tmp_path):
        char = base_character()
        char['custom_stats']['sleep'] = {"current": 40, "min": 0, "max": 100}

        rules = {
            "rules": [
                {"stat": "sleep", "per_hour": -3, "sleep_restore_per_hour": 12.5},
                {"stat": "hunger", "per_hour": -1}
            ]
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(4, sleeping=True)

        sleep_change = next((c for c in result['stat_changes'] if c['stat'] == 'sleep'), None)
        assert sleep_change is not None
        assert sleep_change['change'] > 0

    def test_sleep_without_flag_drains(self, tmp_path):
        char = base_character()
        char['custom_stats']['sleep'] = {"current": 80, "min": 0, "max": 100}

        rules = {
            "rules": [
                {"stat": "sleep", "per_hour": -3, "sleep_restore_per_hour": 12.5}
            ]
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2, sleeping=False)

        sleep_change = next((c for c in result['stat_changes'] if c['stat'] == 'sleep'), None)
        assert sleep_change is not None
        assert sleep_change['change'] < 0


# ─── Tests: Conditional Effects ────────────────────────────

class TestConditionalEffects:
    def test_heal_only_when_hp_below_max(self, tmp_path):
        char = base_character()
        char['hp']['current'] = 30

        rules = {
            "rules": [
                {"stat": "hp", "per_hour": 3, "condition": "hp < max"}
            ]
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2)

        hp_change = next((c for c in result['stat_changes'] if c['stat'] == 'hp'), None)
        assert hp_change is not None
        assert hp_change['change'] > 0

    def test_no_heal_when_hp_at_max(self, tmp_path):
        char = base_character()
        char['hp']['current'] = 40

        rules = {
            "rules": [
                {"stat": "hp", "per_hour": 3, "condition": "hp < max"}
            ]
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2)

        hp_change = next((c for c in result['stat_changes'] if c['stat'] == 'hp'), None)
        assert hp_change is None


# ─── Tests: Stat Consequences ──────────────────────────────

class TestStatConsequences:
    def test_hunger_zero_triggers_damage(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['current'] = 0

        rules = {
            "rules": [{"stat": "hunger", "per_hour": -2}],
            "stat_consequences": {
                "starvation": {
                    "condition": {"stat": "hunger", "operator": "<=", "value": 0},
                    "effects": [
                        {"type": "hp_damage", "amount": -1, "per_hour": True},
                        {"type": "message", "text": "You are starving!"}
                    ]
                }
            }
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2)

        assert len(result['stat_consequences']) > 0
        msg = result['stat_consequences'][0]
        assert msg['name'] == 'starvation'
        assert 'starving' in msg['message'].lower()

    def test_high_radiation_adds_condition(self, tmp_path):
        char = base_character()
        char['custom_stats']['radiation']['current'] = 150

        rules = {
            "rules": [{"stat": "radiation", "per_hour": 1}],
            "stat_consequences": {
                "rad_sickness": {
                    "condition": {"stat": "radiation", "operator": ">=", "value": 100},
                    "effects": [
                        {"type": "condition", "name": "Radiation Sickness"}
                    ]
                }
            }
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        engine.tick(1)

        updated_char = engine.player_mgr.get_player("TestHero")
        conditions = updated_char.get('conditions', [])
        assert "Radiation Sickness" in conditions

    def test_consequence_not_triggered_when_above_threshold(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['current'] = 50

        rules = {
            "rules": [{"stat": "hunger", "per_hour": -2}],
            "stat_consequences": {
                "starvation": {
                    "condition": {"stat": "hunger", "operator": "<=", "value": 0},
                    "effects": [
                        {"type": "message", "text": "Starving!"}
                    ]
                }
            }
        }
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2)

        assert result['stat_consequences'] == []


# ─── Tests: effects_per_hour Fallback ──────────────────────

class TestEffectsPerHourFallback:
    def test_old_format_works(self, tmp_path):
        campaign = base_campaign()
        campaign['campaign_rules']['time_effects'] = {
            "enabled": True,
            "effects_per_hour": {
                "hunger": -5,
                "thirst": -3
            },
            "stat_consequences": {}
        }
        ws = make_campaign(tmp_path, campaign, base_character())
        engine = make_engine(ws)

        result = engine.tick(2)

        hunger_change = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger_change is not None
        assert hunger_change['change'] == -10


# ─── Tests: Edge Cases ─────────────────────────────────────

class TestEdgeCases:
    def test_no_character(self, tmp_path):
        campaign = base_campaign()
        campaign['current_character'] = None
        ws = make_campaign(tmp_path, campaign, base_character())
        engine = make_engine(ws)

        result = engine.tick(2)
        assert result['stat_changes'] == []

    def test_character_without_custom_stats(self, tmp_path):
        char = base_character()
        del char['custom_stats']
        rules = {"rules": [{"stat": "hunger", "per_hour": -2}]}
        ws = make_campaign(tmp_path, base_campaign(rules), char)
        engine = make_engine(ws)

        result = engine.tick(2)
        assert result['stat_changes'] == []

    def test_empty_rules(self, tmp_path):
        rules = {"rules": []}
        ws = make_campaign(tmp_path, base_campaign(rules), base_character())
        engine = make_engine(ws)

        result = engine.tick(5)
        assert result['stat_changes'] == []

    def test_no_rules_no_effects_per_hour(self, tmp_path):
        campaign = base_campaign()
        campaign['campaign_rules']['time_effects'] = {
            "enabled": True,
            "stat_consequences": {}
        }
        ws = make_campaign(tmp_path, campaign, base_character())
        engine = make_engine(ws)

        result = engine.tick(2)
        assert result['stat_changes'] == []


# ─── Tests: Status Display ─────────────────────────────────

class TestStatus:
    def test_status_returns_stats(self, tmp_path, capsys):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        stats = engine.status()

        assert 'hunger' in stats
        assert 'thirst' in stats
        assert 'radiation' in stats

        captured = capsys.readouterr()
        assert 'hunger' in captured.out.lower()

    def test_status_no_custom_stats(self, tmp_path, capsys):
        char = base_character()
        del char['custom_stats']
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        stats = engine.status()
        assert stats == {}

        captured = capsys.readouterr()
        assert 'no custom stats' in captured.out.lower()


# ─── Tests: Persistence ───────────────────────────────────

class TestPersistence:
    def test_tick_persists_stat_changes(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.tick(3)

        char = engine.player_mgr.get_player("TestHero")
        assert char['custom_stats']['hunger']['value'] < 80
        assert char['custom_stats']['thirst']['value'] < 70
        assert char['custom_stats']['radiation']['value'] > 10

    def test_consecutive_ticks_accumulate(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.tick(1)
        engine.tick(1)

        char = engine.player_mgr.get_player("TestHero")
        assert char['custom_stats']['hunger']['value'] == 76
        assert char['custom_stats']['thirst']['value'] == 64


# ─── Tests: Rate Modifiers ────────────────────────────────

class TestRateModifiers:
    def test_modifier_slows_drain(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['rate_modifier'] = 1
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        result = engine.tick(2)
        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] == -2  # base -2 + mod +1 = -1 per hour, 2 hours = -2

    def test_modifier_speeds_drain(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['rate_modifier'] = -3
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        result = engine.tick(1)
        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] == -5  # base -2 + mod -3 = -5

    def test_modifier_reverses_drain(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['rate_modifier'] = 5
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        result = engine.tick(2)
        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] > 0  # base -2 + mod +5 = +3

    def test_set_rate_modifier_reset(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['rate_modifier'] = 5
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        result = engine.set_rate_modifier('hunger', 'reset')
        assert result['new_modifier'] == 0

    def test_set_rate_modifier_set(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.set_rate_modifier('hunger', 'set 7')
        assert result['new_modifier'] == 7

    def test_set_rate_modifier_delta(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.set_rate_modifier('hunger', '+3')
        result = engine.set_rate_modifier('hunger', '+2')
        assert result['new_modifier'] == 5

    def test_no_modifier_backward_compat(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(2)
        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] == -4  # base -2, no modifier, 2 hours


# ─── Tests: Blocked By ────────────────────────────────────

class TestBlockedBy:
    def _campaign_with_blocked(self):
        return base_campaign({
            "rules": [
                {"stat": "hunger", "per_hour": -2},
                {"stat": "health", "per_hour": 2, "blocked_by": [
                    {"stat": "hunger", "operator": "<=", "value": 30}
                ]}
            ]
        })

    def _char_with_health(self, hunger_val=80):
        char = base_character()
        char['custom_stats']['health'] = {"current": 50, "min": 0, "max": 100}
        char['custom_stats']['hunger']['current'] = hunger_val
        return char

    def test_blocked_when_hungry(self, tmp_path):
        ws = make_campaign(tmp_path, self._campaign_with_blocked(), self._char_with_health(hunger_val=20))
        engine = make_engine(ws)

        result = engine.tick(2)
        health = next((c for c in result['stat_changes'] if c['stat'] == 'health'), None)
        assert health is None  # blocked because hunger <= 30

    def test_not_blocked_when_fed(self, tmp_path):
        ws = make_campaign(tmp_path, self._campaign_with_blocked(), self._char_with_health(hunger_val=80))
        engine = make_engine(ws)

        result = engine.tick(2)
        health = next((c for c in result['stat_changes'] if c['stat'] == 'health'), None)
        assert health is not None
        assert health['change'] > 0

    def test_blocked_any_of_multiple(self, tmp_path):
        campaign = base_campaign({
            "rules": [
                {"stat": "health", "per_hour": 2, "blocked_by": [
                    {"stat": "hunger", "operator": "<=", "value": 30},
                    {"stat": "thirst", "operator": "<=", "value": 30}
                ]}
            ]
        })
        char = self._char_with_health(hunger_val=80)
        char['custom_stats']['thirst']['current'] = 10  # thirst blocks
        ws = make_campaign(tmp_path, campaign, char)
        engine = make_engine(ws)

        result = engine.tick(2)
        health = next((c for c in result['stat_changes'] if c['stat'] == 'health'), None)
        assert health is None

    def test_negative_rate_not_blocked(self, tmp_path):
        campaign = base_campaign({
            "rules": [
                {"stat": "hunger", "per_hour": -4, "blocked_by": [
                    {"stat": "thirst", "operator": "<=", "value": 30}
                ]}
            ]
        })
        char = base_character()
        char['custom_stats']['thirst']['current'] = 10
        ws = make_campaign(tmp_path, campaign, char)
        engine = make_engine(ws)

        result = engine.tick(2)
        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] < 0  # negative rate not blocked

    def test_backward_compat_no_blocked_by(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(2)
        assert len(result['stat_changes']) > 0

    def test_blocked_by_missing_stat_ignored(self, tmp_path):
        campaign = base_campaign({
            "rules": [
                {"stat": "health", "per_hour": 2, "blocked_by": [
                    {"stat": "nonexistent", "operator": "<=", "value": 30}
                ]}
            ]
        })
        char = self._char_with_health()
        ws = make_campaign(tmp_path, campaign, char)
        engine = make_engine(ws)

        result = engine.tick(2)
        health = next((c for c in result['stat_changes'] if c['stat'] == 'health'), None)
        assert health is not None
        assert health['change'] > 0


# ─── Tests: Show Rates ────────────────────────────────────

class TestShowRates:
    def test_rates_returns_rows(self, tmp_path, capsys):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        rows = engine.show_rates()
        assert len(rows) == 3

        captured = capsys.readouterr()
        assert 'hunger' in captured.out.lower()

    def test_rates_with_modifier(self, tmp_path):
        char = base_character()
        char['custom_stats']['hunger']['rate_modifier'] = 5
        ws = make_campaign(tmp_path, base_campaign(), char)
        engine = make_engine(ws)

        rows = engine.show_rates()
        hunger_row = next(r for r in rows if r['stat'] == 'hunger')
        assert hunger_row['modifier'] == 5
        assert hunger_row['effective'] == 3  # base -2 + mod 5 = 3


# ─── Tests: Timed Effects (Buffs/Debuffs) ─────────────────

class TestTimedEffects:
    def test_rate_bonus_applied_in_tick(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Антирадин", [{"stat": "radiation", "rate_bonus": -5}], duration_hours=4)
        result = engine.tick(2)

        rad = next((c for c in result['stat_changes'] if c['stat'] == 'radiation'), None)
        assert rad is not None
        assert rad['change'] == -8  # base +1 + bonus -5 = -4/h, 2h = -8

    def test_per_hour_applied_in_tick(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Хилка", [{"stat": "hunger", "per_hour": 3}], duration_hours=4)
        result = engine.tick(2)

        hunger = next((c for c in result['stat_changes'] if c['stat'] == 'hunger'), None)
        assert hunger is not None
        assert hunger['change'] == 2  # base -2/h + per_hour +3/h = +1/h, 2h = +2

    def test_instant_applied_on_add(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Яд", [{"stat": "radiation", "instant": 50}], duration_hours=1)

        char_data = engine.json_ops.load_json("character.json")
        assert char_data['custom_stats']['radiation']['value'] == 60  # 10 + 50

    def test_instant_hp(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Зелье", [{"stat": "hp", "instant": 5}], duration_hours=1)

        char_data = engine.json_ops.load_json("character.json")
        assert char_data['hp']['current'] == 35  # 30 + 5

    def test_effect_expires_after_duration(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Short", [{"stat": "radiation", "rate_bonus": -10}], duration_hours=2)
        engine.tick(3)

        char_data = engine.json_ops.load_json("character.json")
        assert len(char_data.get('active_effects', [])) == 0

    def test_stackable_true_stacks(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -2}], duration_hours=4, stackable=True)
        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -2}], duration_hours=4, stackable=True)

        char_data = engine.json_ops.load_json("character.json")
        buffs = [e for e in char_data['active_effects'] if e['name'] == 'Buff']
        assert len(buffs) == 2

    def test_stackable_false_replaces(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -2}], duration_hours=4, stackable=False)
        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -5}], duration_hours=6, stackable=False)

        char_data = engine.json_ops.load_json("character.json")
        buffs = [e for e in char_data['active_effects'] if e['name'] == 'Buff']
        assert len(buffs) == 1
        assert buffs[0]['effects'][0]['rate_bonus'] == -5
        assert buffs[0]['duration_hours'] == 6

    def test_remove_effect(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -2}], duration_hours=4)
        engine.add_effect("Buff", [{"stat": "radiation", "rate_bonus": -3}], duration_hours=4)
        removed = engine.remove_effect("Buff")

        assert removed == 2
        char_data = engine.json_ops.load_json("character.json")
        assert len(char_data.get('active_effects', [])) == 0

    def test_list_effects(self, tmp_path, capsys):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Антирадин", [{"stat": "radiation", "rate_bonus": -10}], duration_hours=4)
        effects = engine.list_effects()

        assert len(effects) == 1
        assert effects[0]['name'] == 'Антирадин'

        captured = capsys.readouterr()
        assert 'Антирадин' in captured.out

    def test_backward_compat_no_active_effects(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(2)
        assert len(result['stat_changes']) > 0

    def test_show_rates_with_effect_bonus(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Антирадин", [{"stat": "radiation", "rate_bonus": -5}], duration_hours=4)
        rows = engine.show_rates()

        rad_row = next(r for r in rows if r['stat'] == 'radiation')
        assert rad_row['effect_bonus'] == -5
        assert rad_row['effective'] == -4  # base 1 + effect -5

    def test_expired_in_report(self, tmp_path, capsys):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Short", [{"stat": "radiation", "rate_bonus": -10}], duration_hours=1)
        engine.tick(2)

        captured = capsys.readouterr()
        assert 'EXPIRED' in captured.out
        assert 'Short' in captured.out

    def test_multiple_stats_one_effect(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Яд", [
            {"stat": "radiation", "rate_bonus": 5},
            {"stat": "hunger", "rate_bonus": -1}
        ], duration_hours=4)

        rows = engine.show_rates()
        rad_row = next(r for r in rows if r['stat'] == 'radiation')
        hunger_row = next(r for r in rows if r['stat'] == 'hunger')
        assert rad_row['effect_bonus'] == 5
        assert hunger_row['effect_bonus'] == -1

    def test_instant_clamped_to_max(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        engine.add_effect("Megadose", [{"stat": "radiation", "instant": 9999}], duration_hours=1)

        char_data = engine.json_ops.load_json("character.json")
        assert char_data['custom_stats']['radiation']['value'] == 500  # clamped to max


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestSleepRate:
    def test_sleep_rate_slows_drain(self, tmp_path):
        override = {
            "rules": [
                {"stat": "hunger", "per_hour": -2, "sleep_rate": -0.5},
                {"stat": "thirst", "per_hour": -3, "sleep_rate": -1},
            ],
        }
        ws = make_campaign(tmp_path, base_campaign(override), base_character())
        engine = make_engine(ws)

        result = engine.tick(4, sleeping=True)
        changes = {c['stat']: c['change'] for c in result['stat_changes']}
        assert changes['hunger'] == -2.0   # -0.5/h * 4h
        assert changes['thirst'] == -4.0   # -1/h * 4h

    def test_no_sleep_rate_uses_full_drain(self, tmp_path):
        ws = make_campaign(tmp_path, base_campaign(), base_character())
        engine = make_engine(ws)

        result = engine.tick(4, sleeping=True)
        changes = {c['stat']: c['change'] for c in result['stat_changes']}
        assert changes['hunger'] == -8.0   # -2/h * 4h (no sleep_rate = full speed)
        assert changes['thirst'] == -12.0  # -3/h * 4h

    def test_sleep_restores_sleep_stat(self, tmp_path):
        override = {
            "rules": [
                {"stat": "sleep", "per_hour": -3, "sleep_restore_per_hour": 10},
            ],
        }
        char = base_character()
        char['custom_stats']['sleep'] = {"current": 30, "min": 0, "max": 100}
        ws = make_campaign(tmp_path, base_campaign(override), char)
        engine = make_engine(ws)

        result = engine.tick(4, sleeping=True)
        changes = {c['stat']: c['change'] for c in result['stat_changes']}
        assert changes['sleep'] == 40.0  # +10/h * 4h


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
