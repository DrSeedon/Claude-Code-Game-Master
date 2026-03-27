#!/usr/bin/env python3
"""
Survival Engine — standalone module for custom stats time effects.

Imports CORE's PlayerManager and JsonOperations. CORE has zero knowledge of this module.
DM (Claude) calls this via dm-survival.sh after time advances.
"""

import argparse
import copy
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "infrastructure"))

from lib.json_ops import JsonOperations
from lib.player_manager import PlayerManager
from lib.campaign_manager import CampaignManager
from lib.currency import load_config as load_currency_config, format_money, migrate_gold
from module_data import ModuleDataManager


class SurvivalEngine:
    """Apply time-based effects to custom stats and check stat consequences."""

    def __init__(self, world_state_dir: str = "world-state"):
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign.")

        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.player_mgr = PlayerManager(str(self.campaign_dir.parent.parent))
        self.module_data_mgr = ModuleDataManager(self.campaign_dir)

    def _normalize_custom_stats(self, char: dict) -> dict:
        """Normalize custom_stats: convert {value, min, max} → {current, min, max}"""
        for stat_data in char.get('custom_stats', {}).values():
            if isinstance(stat_data, dict) and 'current' not in stat_data and 'value' in stat_data:
                stat_data['current'] = stat_data['value']
        return char

    def _load_module_config(self) -> dict:
        data = self.module_data_mgr.load("custom-stats")
        if not data:
            raise RuntimeError("No custom-stats config found. Expected: module-data/custom-stats.json")
        return data

    def _load_custom_stats(self) -> dict:
        data = self.module_data_mgr.load("custom-stats")
        return data.get('character_stats', {})

    def _save_custom_stats(self, stats: dict):
        data = self.module_data_mgr.load("custom-stats")
        data['character_stats'] = stats
        self.module_data_mgr.save("custom-stats", data)

    def _inject_stats(self, char: dict) -> dict:
        char['custom_stats'] = self._load_custom_stats()
        return char

    def _persist_stats(self, char: dict):
        stats = char.pop('custom_stats', {})
        if stats:
            self._save_custom_stats(stats)

    def _load_char_with_stats(self) -> dict:
        char_data = self.json_ops.load_json("character.json")
        char_data['custom_stats'] = self._load_custom_stats()
        return char_data

    def _save_char_with_stats(self, char_data: dict):
        stats = char_data.pop('custom_stats', {})
        self.json_ops.save_json("character.json", char_data)
        if stats:
            self._save_custom_stats(stats)

    def tick(self, elapsed_hours: float, sleeping: bool = False) -> dict:
        """
        Main entry point. Apply time effects + check stat consequences.

        Returns dict with stat_changes, stat_consequences lists.
        """
        time_effects = self._load_module_config()

        if not time_effects.get('enabled'):
            print("[SKIP] Time effects not enabled for this campaign")
            return {'stat_changes': [], 'stat_consequences': []}

        campaign = self.json_ops.load_json("campaign-overview.json")
        char_name = campaign.get('current_character')
        if not char_name:
            print("[SKIP] No active character")
            return {'stat_changes': [], 'stat_consequences': []}

        stat_changes = self._apply_time_effects(elapsed_hours, time_effects, char_name, sleeping=sleeping)
        stat_consequences = self._check_stat_consequences(elapsed_hours, time_effects, char_name)

        self._print_report(stat_changes, stat_consequences)

        triggered = self._check_time_consequences(elapsed_hours) if hasattr(self, '_check_time_consequences') else []
        if triggered:
            print("\n⚠️  Timed Consequences Triggered:")
            for tc in triggered:
                print(f"  [{tc.get('id', '?')}] {tc.get('consequence', tc.get('event', ''))}")

        expense_results = self._process_recurring_expenses(elapsed_hours) if hasattr(self, '_process_recurring_expenses') else []
        if expense_results:
            self._print_expense_report(expense_results)

        income_results = self._process_recurring_income(elapsed_hours) if hasattr(self, '_process_recurring_income') else []
        if income_results:
            self._print_income_report(income_results)
            work_hours = sum(r.get('hours_spent', 0) for r in income_results)
            if work_hours > 0:
                work_stats = self._tick_stats_only(work_hours, sleeping=False)
                if work_stats:
                    B = "\033[1m"; RS = "\033[0m"
                    print(f"\n  {B}⏱️  Work Time Effects ({work_hours}ч):{RS}")
                    self._print_stat_changes(work_stats)

        production_results = self._process_recurring_production(elapsed_hours) if hasattr(self, '_process_recurring_production') else []
        if production_results:
            self._print_production_report(production_results)

        random_event = self._roll_random_event(elapsed_hours) if hasattr(self, '_roll_random_event') else None
        if random_event:
            self._print_random_event(random_event)

        return {
            'stat_changes': stat_changes,
            'stat_consequences': stat_consequences,
            'expense_results': expense_results,
            'random_event': random_event,
        }

    def status(self) -> dict:
        """Show current custom stats for active character."""
        campaign = self.json_ops.load_json("campaign-overview.json")
        char_name = campaign.get('current_character')
        if not char_name:
            print("[ERROR] No active character")
            return {}

        char = self.player_mgr.get_player(char_name)
        if not char:
            print(f"[ERROR] Character '{char_name}' not found")
            return {}

        char = self._inject_stats(char)
        char = self._normalize_custom_stats(char)
        custom_stats = char.get('custom_stats', {})
        if not custom_stats:
            print(f"[INFO] {char_name} has no custom stats")
            return {}

        C = "\033[36m"; B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
        Y = "\033[33m"; R = "\033[31m"; G = "\033[32m"
        print(f"  {B}📊 CUSTOM STATS:{RS} {char_name}")
        for stat_name, stat_data in custom_stats.items():
            current = stat_data['current']
            max_val = stat_data.get('max')
            if max_val is not None:
                bar_len = 20
                pct = current / max_val if max_val > 0 else 0
                fill = int(pct * bar_len)
                bar_color = G if pct < 0.3 else Y if pct < 0.6 else R
                bar = f"{bar_color}{'█' * fill}{DM}{'░' * (bar_len - fill)}{RS}"
                print(f"  {stat_name:12s} {bar} {C}{int(current):>3}{RS}/{max_val}")
            else:
                print(f"  {stat_name}: {C}{current}{RS}")

        return custom_stats

    def _is_blocked(self, blocked_by: list, char: dict) -> bool:
        """Check if any blocked_by condition is met. Each item: {stat, operator, value}."""
        for block in blocked_by:
            stat_name = block.get('stat')
            operator = block.get('operator', '<=')
            threshold = block.get('value', 0)

            cs = char.get('custom_stats', {}).get(stat_name)
            if cs is None:
                continue

            current = cs.get('current', cs.get('value', 0))
            if operator == '<=' and current <= threshold:
                return True
            elif operator == '>=' and current >= threshold:
                return True
            elif operator == '<' and current < threshold:
                return True
            elif operator == '>' and current > threshold:
                return True
            elif operator == '==' and current == threshold:
                return True
        return False

    def add_effect(self, name: str, effects: list, duration_hours: float,
                   stackable: bool = True, char_name: str = None) -> dict:
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self._load_char_with_stats()
        active_effects = char_data.setdefault('active_effects', [])

        if not stackable:
            active_effects[:] = [e for e in active_effects if e['name'] != name]

        effect_entry = {
            'name': name,
            'effects': effects,
            'duration_hours': duration_hours,
            'remaining_hours': duration_hours,
            'stackable': stackable
        }
        active_effects.append(effect_entry)

        has_instant_hp = False
        for eff in effects:
            if 'instant' in eff:
                stat = eff['stat']
                amount = eff['instant']
                if stat == 'hp':
                    self.player_mgr.modify_hp(char_name, int(amount))
                    has_instant_hp = True
                else:
                    cs = char_data.get('custom_stats', {}).get(stat)
                    if cs:
                        cur = round(cs.get('current', cs.get('value', 0)), 2)
                        new_val = round(cur + amount, 2)
                        cs_max = cs.get('max')
                        cs_min = cs.get('min', 0)
                        if cs_max is not None:
                            new_val = min(new_val, cs_max)
                        if cs_min is not None:
                            new_val = max(new_val, cs_min)
                        cs['value'] = round(new_val, 2)
                        cs.pop('current', None)

        if has_instant_hp:
            fresh = self._load_char_with_stats()
            fresh['active_effects'] = char_data['active_effects']
            fresh['custom_stats'] = char_data.get('custom_stats', fresh.get('custom_stats', {}))
            char_data = fresh

        self._save_char_with_stats(char_data)
        print(f"[EFFECT] Added '{name}' for {duration_hours}h (stackable={stackable})")
        return effect_entry

    def remove_effect(self, name: str, char_name: str = None) -> int:
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self._load_char_with_stats()
        active_effects = char_data.get('active_effects', [])
        before = len(active_effects)
        char_data['active_effects'] = [e for e in active_effects if e['name'] != name]
        removed = before - len(char_data['active_effects'])
        self._save_char_with_stats(char_data)
        print(f"[EFFECT] Removed {removed} effect(s) named '{name}'")
        return removed

    def list_effects(self, char_name: str = None) -> list:
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self._load_char_with_stats()
        active_effects = char_data.get('active_effects', [])

        C = "\033[36m"; B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
        G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"; M = "\033[35m"

        if not active_effects:
            print(f"\n  {DM}No active effects{RS}")
            return []

        print(f"\n  {B}✦ Active Effects:{RS}")
        print(f"  {DM}{'Name':<22} {'Remaining':>10} {'Duration':>10} {'Details'}{RS}")
        print(f"  {DM}{'─'*22} {'─'*10} {'─'*10} {'─'*30}{RS}")
        for eff in active_effects:
            details = []
            for e in eff['effects']:
                parts = [f"{C}{e['stat']}{RS}"]
                if 'rate_bonus' in e:
                    v = e['rate_bonus']
                    color = G if v < 0 else R
                    parts.append(f"{color}rate {v:+g}{RS}")
                if 'per_hour' in e:
                    v = e['per_hour']
                    color = G if v > 0 else R
                    parts.append(f"{color}{v:+g}/h{RS}")
                if 'instant' in e:
                    v = e['instant']
                    color = G if v > 0 else R
                    parts.append(f"{color}instant {v:+g}{RS}")
                details.append(' '.join(parts))
            detail_str = ', '.join(details)
            rem = eff['remaining_hours']
            rem_color = G if rem > 2 else Y if rem > 0.5 else R
            print(f"  {M}{eff['name']:<22}{RS} {rem_color}{rem:>9.1f}h{RS} {DM}{eff['duration_hours']:>9.1f}h{RS} {detail_str}")

        return active_effects

    def set_rate_modifier(self, stat: str, value: str, char_name: str = None) -> dict:
        """Set rate_modifier for a stat. value: '+N', '-N', 'set N', 'reset'."""
        if char_name is None:
            char_name = self._get_active_character_name()

        custom_stats = self._load_custom_stats()
        cs = custom_stats.get(stat)
        if cs is None:
            raise RuntimeError(f"Custom stat '{stat}' not found")

        old_mod = cs.get('rate_modifier', 0)

        if value == 'reset':
            new_mod = 0
        elif value.startswith('set '):
            new_mod = float(value[4:])
        else:
            new_mod = old_mod + float(value)

        cs['rate_modifier'] = new_mod
        self._save_custom_stats(custom_stats)
        return {'stat': stat, 'old_modifier': old_mod, 'new_modifier': new_mod}

    def show_rates(self, char_name: str = None) -> list:
        """Show effective rates for all stats. Returns list of rate info dicts."""
        if char_name is None:
            char_name = self._get_active_character_name()

        time_effects = self._load_module_config()
        rules = time_effects.get('rules', [])
        if not rules:
            effects_per_hour = time_effects.get('effects_per_hour', {})
            if effects_per_hour:
                rules = [{'stat': s, 'per_hour': c} for s, c in effects_per_hour.items()]

        char_data = self._load_char_with_stats()
        char = self.player_mgr.get_player(char_name)
        if char:
            char = self._inject_stats(char)
            char = self._normalize_custom_stats(char)

        active_effects = char_data.get('active_effects', [])

        rows = []
        for rule in rules:
            stat = rule['stat']
            base = rule.get('per_hour', rule.get('change_per_hour', 0))
            cs = char_data.get('custom_stats', {}).get(stat, {})
            mod = cs.get('rate_modifier', 0)

            effect_bonus = sum(
                e.get('rate_bonus', 0)
                for eff in active_effects
                for e in eff.get('effects', [])
                if e.get('stat') == stat and 'rate_bonus' in e
            )

            blocked_by = rule.get('blocked_by', [])
            blocked = False
            if blocked_by and char and (base + mod + effect_bonus) > 0:
                blocked = self._is_blocked(blocked_by, char)

            effective = 0.0 if blocked else (base + mod + effect_bonus)

            rows.append({
                'stat': stat, 'base': base, 'modifier': mod,
                'effect_bonus': effect_bonus,
                'blocked': blocked, 'effective': effective
            })

        def _fmt_rate(v):
            if v == 0:
                return "0"
            if abs(v) < 0.1:
                daily = v * 24
                return f"{daily:+.1f}/d"
            return f"{v:+.1f}/h"

        C = "\033[36m"; B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
        G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"; M = "\033[35m"

        def _color_rate(v):
            if v == 0:
                return f"{DM}     —{RS}"
            raw = _fmt_rate(v)
            color = G if v < 0 else R
            return f"{color}{raw:>6}{RS}"

        print(f"\n  {B}⚙ Rate Table:{RS}")
        print(f"  {DM}{'Stat':<14}{'Base':>6}  {'Mod':>6}  {'Effects':>6}  {'Blocked':>7}  {'Effective':>9}{RS}")
        print(f"  {DM}{'─'*14}{'─'*6}──{'─'*6}──{'─'*6}──{'─'*7}──{'─'*9}{RS}")
        for r in rows:
            bl = f"{R}BLOCKED{RS}" if r['blocked'] else f"{DM}      —{RS}"
            print(f"  {C}{r['stat']:<14}{RS}{_color_rate(r['base'])}  {_color_rate(r['modifier'])}  {_color_rate(r['effect_bonus'])}  {bl}  {_color_rate(r['effective'])}")

        return rows

    def _apply_time_effects(self, elapsed_hours: float, time_effects: dict, char_name: str, sleeping: bool = False) -> list:
        """Apply per-tick stat changes based on time_effects rules."""
        char = self.player_mgr.get_player(char_name)
        if not char:
            return []
        char = self._inject_stats(char)
        char = self._normalize_custom_stats(char)

        rules = time_effects.get('rules', [])
        if not rules:
            effects_per_hour = time_effects.get('effects_per_hour', {})
            if effects_per_hour:
                rules = [{'stat': stat, 'per_hour': change} for stat, change in effects_per_hour.items()]

        if not rules:
            return []

        char_data = self._load_char_with_stats()
        active_effects = char_data.get('active_effects', [])

        sim_char = copy.deepcopy(char)

        def _apply_stat_change(sim, stat, amount):
            if stat == 'hp':
                sim['hp']['current'] = max(0, min(
                    sim['hp']['current'] + int(amount),
                    sim['hp']['max']
                ))
            else:
                cs = sim.get('custom_stats', {}).get(stat)
                if cs:
                    new_val = cs['current'] + amount
                    cs_max = cs.get('max')
                    cs_min = cs.get('min', 0)
                    if cs_max is not None:
                        new_val = min(new_val, cs_max)
                    if cs_min is not None:
                        new_val = max(new_val, cs_min)
                    cs['current'] = new_val

        expired_names = []

        for _ in range(int(elapsed_hours)):
            for rule in rules:
                stat = rule['stat']
                change_per_hour = rule.get('per_hour', rule.get('change_per_hour', 0))

                if 'per_hour_formula' in rule:
                    formula_vars = {
                        name: data['current']
                        for name, data in sim_char.get('custom_stats', {}).items()
                    }
                    try:
                        change_per_hour = float(eval(rule['per_hour_formula'], {"__builtins__": {}}, formula_vars))
                    except Exception:
                        pass

                if sleeping:
                    if stat == 'sleep':
                        change_per_hour = rule.get('sleep_restore_per_hour', 12.5)
                    elif 'sleep_rate' in rule:
                        change_per_hour = rule['sleep_rate']

                condition = rule.get('condition')
                if condition and not self._check_rule_condition(condition, sim_char):
                    continue

                cs_data = char_data.get('custom_stats', {}).get(stat, {})
                rate_mod = cs_data.get('rate_modifier', 0)
                change_per_hour += rate_mod

                effect_rate_bonus = sum(
                    e.get('rate_bonus', 0)
                    for eff in active_effects
                    if eff.get('remaining_hours', 0) > 0
                    for e in eff.get('effects', [])
                    if e.get('stat') == stat and 'rate_bonus' in e
                )
                change_per_hour += effect_rate_bonus

                blocked_by = rule.get('blocked_by', [])
                if blocked_by and change_per_hour > 0 and self._is_blocked(blocked_by, sim_char):
                    change_per_hour = 0

                if abs(change_per_hour) < 0.001:
                    continue

                _apply_stat_change(sim_char, stat, change_per_hour)

            for eff in active_effects:
                if eff.get('remaining_hours', 0) <= 0:
                    continue
                for e in eff.get('effects', []):
                    if 'per_hour' in e:
                        _apply_stat_change(sim_char, e['stat'], e['per_hour'])

            for eff in active_effects:
                if eff.get('remaining_hours', 0) > 0:
                    eff['remaining_hours'] -= 1
                    if eff['remaining_hours'] <= 0:
                        expired_names.append(eff['name'])

        effect_only_stats = set()
        for eff in active_effects:
            for e in eff.get('effects', []):
                if 'per_hour' in e:
                    effect_only_stats.add(e['stat'])

        all_stats = set(r['stat'] for r in rules) | effect_only_stats

        changes = []
        for stat in all_stats:
            if stat == 'hp':
                old_val = char['hp']['current']
                new_val = sim_char['hp']['current']
                int_change = new_val - old_val
                if int_change != 0:
                    self.player_mgr.modify_hp(char_name, int_change)
                    char = self.player_mgr.get_player(char_name)
                    changes.append({'stat': 'hp', 'old': old_val, 'new': char['hp']['current'], 'change': int_change})
            else:
                old_cs = char.get('custom_stats', {}).get(stat)
                new_cs = sim_char.get('custom_stats', {}).get(stat)
                if old_cs and new_cs:
                    diff = new_cs['current'] - old_cs['current']
                    if abs(diff) > 0.001:
                        old_val = old_cs['current']
                        current_stats = self._load_custom_stats()
                        cs_entry = current_stats.get(stat)
                        if cs_entry:
                            cs_max = cs_entry.get('max')
                            cs_min = cs_entry.get('min', 0)
                            cur = round(cs_entry.get('current', cs_entry.get('value', 0)), 2)
                            new_val = round(cur + diff, 2)
                            if cs_max is not None:
                                new_val = min(new_val, cs_max)
                            if cs_min is not None:
                                new_val = max(new_val, cs_min)
                            new_val = round(new_val, 2)
                            cs_entry['value'] = new_val
                            cs_entry.pop('current', None)
                            self._save_custom_stats(current_stats)
                            changes.append({'stat': stat, 'old': old_val, 'new': new_val, 'change': diff})

        if active_effects:
            char_data = self.json_ops.load_json("character.json")
            char_data['active_effects'] = [e for e in active_effects if e.get('remaining_hours', 0) > 0]
            self.json_ops.save_json("character.json", char_data)  # active_effects stays in character.json

        if expired_names:
            for name in expired_names:
                print(f"  [EXPIRED] Effect '{name}' has worn off")

        return changes

    def _check_rule_condition(self, condition: str, char: dict) -> bool:
        """Check if a rule condition is met. Supports: 'hp < max', 'stat:name < value'"""
        try:
            parts = condition.split()
            if len(parts) != 3:
                return True

            target, operator, value_str = parts

            if target == 'hp':
                current = char['hp']['current']
                if value_str == 'max':
                    compare_to = char['hp']['max']
                else:
                    compare_to = float(value_str)
            elif target.startswith('stat:'):
                stat_name = target[5:]
                custom_stats = char.get('custom_stats', {})
                if stat_name not in custom_stats:
                    return True
                current = custom_stats[stat_name]['current']
                if value_str == 'max':
                    compare_to = custom_stats[stat_name].get('max', 999999)
                else:
                    compare_to = float(value_str)
            else:
                return True

            if operator == '<':
                return current < compare_to
            elif operator == '<=':
                return current <= compare_to
            elif operator == '>':
                return current > compare_to
            elif operator == '>=':
                return current >= compare_to
            elif operator == '==':
                return current == compare_to
            elif operator == '!=':
                return current != compare_to
        except (ValueError, KeyError, TypeError):
            pass
        return True

    def _check_stat_consequences(self, elapsed_hours: float, time_effects: dict, char_name: str) -> list:
        """Check and apply stat-based consequences (hunger=0 -> damage, radiation>=100 -> poisoned)."""
        char = self.player_mgr.get_player(char_name)
        if not char:
            return []

        char = self._inject_stats(char)
        char = self._normalize_custom_stats(char)
        custom_stats = char.get('custom_stats', {})
        stat_consequences = time_effects.get('stat_consequences', {})
        triggered = []

        for consequence_name, consequence_data in stat_consequences.items():
            condition = consequence_data['condition']
            stat = condition['stat']
            operator = condition['operator']
            threshold = condition['value']

            if stat not in custom_stats:
                continue

            current_value = custom_stats[stat]['current']

            met = False
            if operator == '<=':
                met = current_value <= threshold
            elif operator == '>=':
                met = current_value >= threshold
            elif operator == '==':
                met = current_value == threshold

            if met:
                for effect in consequence_data.get('effects', []):
                    effect_type = effect['type']

                    if effect_type == 'hp_damage':
                        damage = effect['amount']
                        if effect.get('per_hour'):
                            damage *= int(elapsed_hours)
                        self.player_mgr.modify_hp(char_name, damage)

                    elif effect_type == 'condition':
                        self.player_mgr.modify_condition(char_name, 'add', effect['name'])

                    elif effect_type == 'message':
                        triggered.append({
                            'type': 'stat_consequence',
                            'name': consequence_name,
                            'message': effect['text']
                        })

        return triggered

    def _print_report(self, stat_changes: list, stat_consequences: list):
        """Print survival tick report."""
        C = "\033[36m"; G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
        B = "\033[1m"; RS = "\033[0m"
        if stat_changes:
            print(f"\n  {B}⏱️  Survival Effects:{RS}")
            for change in stat_changes:
                delta = change['change']
                color = R if delta > 0 else G
                sign = '+' if delta > 0 else ''
                print(f"  📊 {change['stat']}: {change['old']} → {C}{change['new']}{RS} {color}({sign}{delta:.2f}){RS}")

        if stat_consequences:
            print(f"\n  {B}⚠️  Stat Consequences:{RS}")
            for sc in stat_consequences:
                print(f"  {Y}⚠ {sc['name']}:{RS} {sc['message']}")

        if not stat_changes and not stat_consequences:
            pass

    def _process_recurring_expenses(self, elapsed_hours: float) -> list:
        if elapsed_hours <= 0:
            return []

        data = self.module_data_mgr.load("custom-stats")
        if not data:
            return []
        expenses = data.get('recurring_expenses', [])
        if not expenses:
            return []

        char = self.json_ops.load_json("character.json")
        if not char:
            return []

        money = char.get('money')
        if money is None:
            money = migrate_gold(char)

        try:
            campaign_dir = self.campaign_mgr.get_active_campaign_dir()
            currency_cfg = load_currency_config(campaign_dir) if campaign_dir else None
        except Exception:
            currency_cfg = None

        results = []
        for exp in expenses:
            exp['accumulated_hours'] = exp.get('accumulated_hours', 0) + elapsed_hours
            interval = exp.get('interval_hours', 24)
            triggers = int(exp['accumulated_hours'] / interval)
            if triggers < 1:
                continue

            exp['accumulated_hours'] = exp['accumulated_hours'] % interval

            cost_dice = exp.get('cost_dice')
            if cost_dice:
                from dice import roll as _dice_roll
                total_cost = sum(_dice_roll(cost_dice) for _ in range(triggers))
            elif 'cost_min' in exp and 'cost_max' in exp:
                total_cost = sum(random.randint(exp['cost_min'], exp['cost_max']) for _ in range(triggers))
            else:
                total_cost = exp.get('cost', 0) * triggers

            if total_cost <= 0:
                continue

            if money >= total_cost:
                money -= total_cost
                results.append({
                    'name': exp.get('name', '?'),
                    'cost': total_cost,
                    'triggers': triggers,
                    'success': True,
                    'remaining': money,
                    'currency_cfg': currency_cfg,
                })
            else:
                results.append({
                    'name': exp.get('name', '?'),
                    'cost': total_cost,
                    'triggers': triggers,
                    'success': False,
                    'remaining': money,
                    'currency_cfg': currency_cfg,
                })

        self.module_data_mgr.save("custom-stats", data)
        char['money'] = money
        if 'gold' in char:
            del char['gold']
        self.json_ops.save_json("character.json", char)

        return results

    def _print_expense_report(self, results: list):
        C = "\033[36m"; R = "\033[31m"; Y = "\033[33m"
        B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"

        print(f"\n  {B}🍞 Recurring Expenses:{RS}")
        for exp in results:
            cfg = exp.get('currency_cfg')
            cost_str = format_money(exp['cost'], cfg)
            rem_str = format_money(exp['remaining'], cfg)
            name = exp['name']
            if exp['success']:
                print(f"  🍞 {name}: {R}-{cost_str}{RS} {DM}({C}{rem_str}{RS}{DM} remaining){RS}")
            else:
                print(f"  {Y}⚠ {name}: НЕ ХВАТАЕТ! Нужно {cost_str}, есть {rem_str}{RS}")

    def _tick_stats_only(self, hours: float, sleeping: bool = False) -> list:
        time_effects = self._load_module_config()
        if not time_effects.get('enabled'):
            return []
        campaign = self.json_ops.load_json("campaign-overview.json")
        char_name = campaign.get('current_character')
        if not char_name:
            return []
        return self._apply_time_effects(hours, time_effects, char_name, sleeping=sleeping)

    def _print_stat_changes(self, changes: list):
        C = "\033[36m"; G = "\033[32m"; R = "\033[31m"; RS = "\033[0m"
        for ch in changes:
            color = G if ch['change'] < 0 else R if ch['change'] > 0 else C
            print(f"  📊 {ch['stat']}: {ch['old']} → {C}{ch['new']}{RS} {color}({ch['change']:+.2f}){RS}")

    def _process_recurring_income(self, elapsed_hours: float) -> list:
        if elapsed_hours <= 0:
            return []
        data = self.module_data_mgr.load("custom-stats")
        if not data:
            return []
        incomes = data.get('recurring_income', [])
        if not incomes:
            return []

        char = self.json_ops.load_json("character.json")
        if not char:
            return []
        money = char.get('money', 0)

        try:
            campaign_dir = self.campaign_mgr.get_active_campaign_dir()
            currency_cfg = load_currency_config(campaign_dir) if campaign_dir else None
        except Exception:
            currency_cfg = None

        from dice import roll as dice_roll

        results = []
        for inc in incomes:
            inc['accumulated_hours'] = inc.get('accumulated_hours', 0) + elapsed_hours
            interval = inc.get('interval_hours', 168)
            triggers = int(inc['accumulated_hours'] / interval)
            if triggers < 1:
                continue
            inc['accumulated_hours'] = inc['accumulated_hours'] % interval

            checks_per = inc.get('checks_per_interval', 1)
            for _ in range(triggers):
              for check_num in range(1, checks_per + 1):
                check = inc.get('check')
                if check:
                    result = self._resolve_income_check(inc, check, dice_roll)
                    if checks_per > 1:
                        result['check_label'] = f"день {check_num}/{checks_per}"
                else:
                    raw = inc.get('income_dice', inc.get('income', 0))
                    if isinstance(raw, str) and 'd' in raw.lower():
                        total = dice_roll(raw)
                        result = {'income': total, 'detail': f"🎲{raw}={total}", 'outcome': 'success', 'hint': None}
                    else:
                        total = int(raw)
                        result = {'income': total, 'detail': None, 'outcome': 'success', 'hint': None}

                hours_per = inc.get('hours_per_check', 0)
                if hours_per:
                    result['hours_spent'] = hours_per

                money += result['income']
                if money < 0:
                    result['debt'] = abs(money)
                    money = 0
                result['remaining'] = money
                result['name'] = inc.get('name', '?')
                result['currency_cfg'] = currency_cfg
                results.append(result)

        self.module_data_mgr.save("custom-stats", data)
        char['money'] = money
        char.pop('gold', None)
        self.json_ops.save_json("character.json", char)
        return results

    def _resolve_income_check(self, inc: dict, check: dict, dice_roll) -> dict:
        dice_expr = check.get('dice', '1d20')
        modifier = check.get('modifier', 0)
        dc = check.get('dc', 10)
        outcomes = inc.get('outcomes', {})

        raw_roll = dice_roll(dice_expr)
        total_roll = raw_roll + modifier
        is_nat1 = (raw_roll == 1)
        is_nat20 = (raw_roll == 20)

        if is_nat1:
            outcome_key = 'crit_fail'
        elif is_nat20:
            outcome_key = 'crit_success'
        elif total_roll < dc:
            outcome_key = 'fail'
        else:
            outcome_key = 'success'

        outcome = outcomes.get(outcome_key, outcomes.get('success', {'income': 0}))
        multiplier = inc.get('income_multiplier', 1)

        raw_income = outcome.get('income_dice', outcome.get('income', 0))
        if isinstance(raw_income, str) and 'd' in raw_income.lower():
            income = dice_roll(raw_income) * multiplier
        else:
            income = int(raw_income) * multiplier

        if outcome_key in ('fail', 'crit_fail'):
            inc['fail_streak'] = inc.get('fail_streak', 0) + 1
        else:
            inc['fail_streak'] = 0

        streak_warn = None
        threshold = inc.get('streak_threshold', 0)
        if threshold > 0 and inc.get('fail_streak', 0) >= threshold:
            streak_warn = inc.get('streak_hint', 'Consecutive failures!')

        detail = f"🎲[{raw_roll}]+{modifier}={total_roll} vs DC {dc}"
        outcome_emoji = {'crit_fail': '💀', 'fail': '✗', 'success': '✓', 'crit_success': '⚔'}
        detail += f" — {outcome_emoji.get(outcome_key, '?')} {outcome_key.upper()}"

        return {
            'income': income,
            'detail': detail,
            'outcome': outcome_key,
            'hint': outcome.get('hint'),
            'streak_warn': streak_warn,
            'raw_roll': raw_roll,
        }

    def _print_income_report(self, results: list):
        C = "\033[36m"; G = "\033[32m"; R = "\033[31m"; Y = "\033[33m"
        B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
        print(f"\n  {B}💰 Recurring Income:{RS}")
        for inc in results:
            cfg = inc.get('currency_cfg')
            amount = inc['income']
            rem_str = format_money(inc['remaining'], cfg)
            detail = f" {inc['detail']}" if inc.get('detail') else ""

            label = inc['name']
            if inc.get('check_label'):
                label += f" ({inc['check_label']})"
            if amount >= 0:
                amt_str = format_money(amount, cfg)
                print(f"  💰 {label}: {G}+{amt_str}{RS}{detail} {DM}({C}{rem_str}{RS}{DM} remaining){RS}")
            else:
                amt_str = format_money(abs(amount), cfg)
                print(f"  💸 {label}: {R}-{amt_str}{RS}{detail} {DM}({C}{rem_str}{RS}{DM} remaining){RS}")

            if inc.get('hours_spent'):
                print(f"     ⏱️  {inc['hours_spent']}ч потрачено")
            if inc.get('hint'):
                print(f"     {DM}[DM: {inc['hint']}]{RS}")
            if inc.get('debt'):
                debt_str = format_money(inc['debt'], cfg)
                print(f"     {R}⚠ ДОЛГ: не хватило {debt_str}! Обнулено до 0.{RS}")
                print(f"     {DM}[DM: нарративные последствия долга — кредитор, голод, потеря репутации]{RS}")
            if inc.get('streak_warn'):
                print(f"     {Y}⚠ STREAK: {inc['streak_warn']}{RS}")

    def _process_recurring_production(self, elapsed_hours: float) -> list:
        if elapsed_hours <= 0:
            return []
        data = self.module_data_mgr.load("custom-stats")
        if not data:
            return []
        productions = data.get('recurring_production', [])
        if not productions:
            return []

        from dice import roll as dice_roll
        sys_path = next(p for p in Path(__file__).parents if (p / ".git").exists())
        sys.path.insert(0, str(sys_path / "lib"))
        from inventory_manager import InventoryManager

        results = []
        for prod in productions:
            prod['accumulated_hours'] = prod.get('accumulated_hours', 0) + elapsed_hours
            interval = prod.get('interval_hours', 24)
            triggers = int(prod['accumulated_hours'] / interval)
            if triggers < 1:
                continue
            prod['accumulated_hours'] = prod['accumulated_hours'] % interval

            target = prod.get('target_inventory', 'Мастерская')
            check = prod.get('check', {})
            outcomes = prod.get('outcomes', {})
            worker = prod.get('worker', prod.get('name', '?'))

            worker_count = prod.get('workers_count', 1)
            for _ in range(triggers):
             for w_num in range(1, worker_count + 1):
                w_label = f" #{w_num}" if worker_count > 1 else ""
                raw_roll = dice_roll(check.get('dice', '1d20'))
                modifier = check.get('modifier', 0)
                dc = check.get('dc', 10)
                total_roll = raw_roll + modifier

                if raw_roll == 1:
                    outcome_key = 'crit_fail'
                elif raw_roll == 20:
                    outcome_key = 'crit_success'
                elif total_roll < dc:
                    outcome_key = 'fail'
                else:
                    outcome_key = 'success'

                outcome = outcomes.get(outcome_key, outcomes.get('success', {}))
                produce = outcome.get('produce', {})
                consume = outcome.get('consume', {})
                hint = outcome.get('hint', '')

                produced_items = {}
                for item, qty_expr in produce.items():
                    if isinstance(qty_expr, str) and 'd' in qty_expr.lower():
                        produced_items[item] = dice_roll(qty_expr)
                    else:
                        produced_items[item] = int(qty_expr)

                consumed_items = {}
                for item, qty_expr in consume.items():
                    if isinstance(qty_expr, str) and 'd' in qty_expr.lower():
                        consumed_items[item] = dice_roll(qty_expr)
                    else:
                        consumed_items[item] = int(qty_expr)

                try:
                    campaign_dir = self.campaign_mgr.get_active_campaign_dir()
                    mgr = InventoryManager(campaign_dir, npc_name=target)
                    ops = {}
                    if produced_items:
                        ops['add'] = {k: v for k, v in produced_items.items()}
                    if consumed_items:
                        ops['remove'] = {k: v for k, v in consumed_items.items()}
                    if ops:
                        mgr.reason = f"{worker}: production"
                        mgr.apply_transaction(ops)
                except Exception:
                    pass

                emoji = {'crit_fail': '💀', 'fail': '✗', 'success': '✓', 'crit_success': '⚔'}
                results.append({
                    'worker': f"{worker}{w_label}",
                    'roll': f"[{raw_roll}]+{modifier}={total_roll} vs DC {dc}",
                    'outcome': outcome_key,
                    'emoji': emoji.get(outcome_key, '?'),
                    'produced': produced_items,
                    'consumed': consumed_items,
                    'hint': hint,
                })

        self.module_data_mgr.save("custom-stats", data)
        return results

    def _print_production_report(self, results: list):
        B = "\033[1m"; RS = "\033[0m"; C = "\033[36m"
        G = "\033[32m"; R = "\033[31m"; DM = "\033[2m"
        print(f"\n  {B}🏭 Production:{RS}")
        for r in results:
            color = G if r['outcome'] in ('success', 'crit_success') else R
            print(f"  {r['emoji']} {r['worker']}: 🎲{r['roll']} — {color}{r['outcome'].upper()}{RS}")
            if r['produced']:
                for item, qty in r['produced'].items():
                    print(f"     {G}+{qty}{RS} {item}")
            if r['consumed']:
                for item, qty in r['consumed'].items():
                    print(f"     {R}-{qty}{RS} {item}")
            if r['hint']:
                print(f"     {DM}[DM: {r['hint']}]{RS}")

    def _roll_random_event(self, elapsed_hours: float) -> dict | None:
        data = self.module_data_mgr.load("custom-stats")
        if not data:
            return None
        event_config = data.get('random_events')
        if not event_config or not event_config.get('enabled', False):
            return None

        interval = event_config.get('interval_hours', 168)
        event_config['accumulated_hours'] = event_config.get('accumulated_hours', 0) + elapsed_hours
        if event_config['accumulated_hours'] < interval:
            self.module_data_mgr.save("custom-stats", data)
            return None

        event_config['accumulated_hours'] = event_config['accumulated_hours'] % interval
        self.module_data_mgr.save("custom-stats", data)

        roll = random.randint(1, 100)
        categories = event_config.get('categories', [
            {"range": [1, 10], "type": "disaster", "emoji": "💀"},
            {"range": [11, 25], "type": "negative", "emoji": "⚠️"},
            {"range": [26, 50], "type": "neutral", "emoji": "📰"},
            {"range": [51, 75], "type": "opportunity", "emoji": "💡"},
            {"range": [76, 95], "type": "positive", "emoji": "🎁"},
            {"range": [96, 100], "type": "windfall", "emoji": "🌟"},
        ])

        event_type = "neutral"
        emoji = "📰"
        for cat in categories:
            r = cat['range']
            if r[0] <= roll <= r[1]:
                event_type = cat['type']
                emoji = cat.get('emoji', '📰')
                break

        scope_roll = random.randint(1, 6)
        scopes = event_config.get('scopes', [
            "personal", "workshop", "npc", "city", "threat", "opportunity"
        ])
        scope = scopes[min(scope_roll - 1, len(scopes) - 1)]

        return {
            'roll': roll,
            'type': event_type,
            'emoji': emoji,
            'scope': scope,
            'scope_roll': scope_roll,
        }

    def _print_random_event(self, event: dict):
        B = "\033[1m"; RS = "\033[0m"; C = "\033[36m"; Y = "\033[33m"
        print(f"\n  {B}🎲 RANDOM EVENT:{RS} {event['emoji']} {Y}{event['type'].upper()}{RS} (d100={C}{event['roll']}{RS})")
        print(f"  Scope: {event['scope']} (d6={event['scope_roll']})")
        print(f"  {B}[DM: narrate an event based on type+scope above]{RS}")

    def _get_active_character_name(self) -> str:
        """Get active character name from campaign overview."""
        campaign = self.json_ops.load_json("campaign-overview.json")
        char_name = campaign.get('current_character')
        if not char_name:
            raise RuntimeError("No active character in campaign")
        return char_name

    def get_custom_stat(self, name: str = None, stat: str = None) -> dict:
        """Get custom stat value. If name is None, uses active character."""
        if name is None:
            name = self._get_active_character_name()

        custom_stats = self._load_custom_stats()
        for stat_data in custom_stats.values():
            if isinstance(stat_data, dict) and 'current' not in stat_data and 'value' in stat_data:
                stat_data['current'] = stat_data['value']

        if stat and stat not in custom_stats:
            raise RuntimeError(f"Custom stat '{stat}' not found for {name}")

        if stat:
            return {stat: custom_stats[stat]}
        return custom_stats

    def modify_custom_stat(self, name: str = None, stat: str = None, amount: float = 0) -> dict:
        """Modify custom stat. Clamp to min/max. If name is None, uses active character."""
        if name is None:
            name = self._get_active_character_name()

        custom_stats = self._load_custom_stats()
        cs = custom_stats.get(stat)
        if cs is None:
            raise RuntimeError(f"Custom stat '{stat}' not found for {name}")

        old_val = round(cs.get('current', cs.get('value', 0)), 2)
        new_val = round(old_val + amount, 2)
        cs_max = cs.get('max')
        cs_min = cs.get('min', 0)
        if cs_max is not None:
            new_val = min(new_val, cs_max)
        if cs_min is not None:
            new_val = max(new_val, cs_min)
        new_val = round(new_val, 2)
        cs['value'] = new_val
        cs.pop('current', None)
        self._save_custom_stats(custom_stats)
        return {'success': True, 'old_value': old_val, 'new_value': new_val}

    def list_custom_stats(self, name: str = None) -> dict:
        """List all custom stats for character."""
        if name is None:
            name = self._get_active_character_name()

        custom_stats = self._load_custom_stats()
        for stat_data in custom_stats.values():
            if isinstance(stat_data, dict) and 'current' not in stat_data and 'value' in stat_data:
                stat_data['current'] = stat_data['value']
        return custom_stats

    def _check_time_consequences(self, elapsed_hours: float) -> list:
        """Check and trigger time-based consequences (trigger_hours field)."""
        consequences = self.json_ops.load_json("consequences.json")
        triggered = []

        for consequence in consequences.get('active', []):
            trigger_hours = consequence.get('trigger_hours')
            if trigger_hours is None:
                continue

            hours_elapsed = consequence.get('hours_elapsed', 0)
            hours_elapsed += elapsed_hours
            consequence['hours_elapsed'] = hours_elapsed

            if hours_elapsed >= trigger_hours:
                triggered.append(consequence)
                consequences.setdefault('resolved', []).append({
                    **consequence,
                    'resolution': f"Auto-triggered after {hours_elapsed:.1f} hours"
                })

        consequences['active'] = [c for c in consequences.get('active', []) if c not in triggered]
        self.json_ops.save_json("consequences.json", consequences)

        return triggered


def main():
    parser = argparse.ArgumentParser(description='Survival Stats Module')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    tick_parser = subparsers.add_parser('tick', help='Apply time effects')
    tick_parser.add_argument('--elapsed', type=float, required=True, help='Hours elapsed')
    tick_parser.add_argument('--sleeping', action='store_true', help='Character is sleeping')

    subparsers.add_parser('status', help='Show current custom stats')

    custom_stat_parser = subparsers.add_parser('custom-stat', help='Get or modify custom stat')
    custom_stat_parser.add_argument('name', nargs='?', help='Character name (optional, auto-detects)')
    custom_stat_parser.add_argument('stat', help='Stat name')
    custom_stat_parser.add_argument('amount', nargs='?', help='Amount to modify (+/- prefix)')
    custom_stat_parser.add_argument('--reason', '-r', help='Reason for change (shown in output)')

    list_parser = subparsers.add_parser('custom-stats-list', help='List all custom stats')
    list_parser.add_argument('name', nargs='?', help='Character name (optional, auto-detects)')

    rate_parser = subparsers.add_parser('rate', help='Set rate modifier for a stat')
    rate_parser.add_argument('stat', help='Stat name')
    rate_parser.add_argument('value', nargs='+', help='+N, -N, set N, or reset')

    subparsers.add_parser('rates', help='Show effective rate table')

    effect_parser = subparsers.add_parser('effect', help='Add or remove timed effect')
    effect_sub = effect_parser.add_subparsers(dest='effect_action')

    effect_add = effect_sub.add_parser('add', help='Add a timed effect')
    effect_add.add_argument('name', help='Effect name')
    effect_add.add_argument('--stat', action='append', required=True, help='Target stat (repeatable)')
    effect_add.add_argument('--rate-bonus', type=float, action='append', default=[], help='Rate bonus per stat')
    effect_add.add_argument('--per-hour', type=float, action='append', default=[], help='Per-hour change per stat')
    effect_add.add_argument('--instant', type=float, action='append', default=[], help='Instant change per stat')
    effect_add.add_argument('--duration', type=float, required=True, help='Duration in hours')
    effect_add.add_argument('--stackable', action='store_true', help='Allow stacking')

    effect_rm = effect_sub.add_parser('remove', help='Remove effect by name')
    effect_rm.add_argument('name', help='Effect name to remove')

    subparsers.add_parser('effects', help='List active timed effects')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        engine = SurvivalEngine()

        if args.action == 'tick':
            engine.tick(args.elapsed, sleeping=args.sleeping)
        elif args.action == 'status':
            engine.status()
        elif args.action == 'custom-stat':
            if not args.stat:
                name = None
                stat = args.name
                amount_str = None
            elif not args.amount:
                if args.stat and (args.stat.startswith('+') or args.stat.startswith('-') or args.stat.replace('.', '', 1).replace('-', '', 1).isdigit()):
                    name = None
                    stat = args.name
                    amount_str = args.stat
                else:
                    name = args.name
                    stat = args.stat
                    amount_str = None
            else:
                name = args.name
                stat = args.stat
                amount_str = args.amount

            if amount_str:
                try:
                    amount = float(amount_str)
                    result = engine.modify_custom_stat(name=name, stat=stat, amount=amount)
                    C = "\033[36m"; G = "\033[32m"; R = "\033[31m"; DM = "\033[2m"; RS = "\033[0m"
                    color = G if amount >= 0 else R
                    reason_str = f" {DM}— {args.reason}{RS}" if getattr(args, 'reason', None) else ""
                    print(f"  📊 {stat}: {result['old_value']} → {C}{result['new_value']}{RS} {color}({amount:+.2f}){RS}{reason_str}")
                except ValueError:
                    print(f"[ERROR] Invalid amount: {amount_str}")
                    sys.exit(1)
            else:
                result = engine.get_custom_stat(name=name, stat=stat)
                stat_data = result[stat]
                current = stat_data['current']
                max_val = stat_data.get('max')
                if max_val is not None:
                    print(f"{stat}: {current}/{max_val}")
                else:
                    print(f"{stat}: {current}")

        elif args.action == 'custom-stats-list':
            stats = engine.list_custom_stats(name=args.name)
            char_name = args.name or engine._get_active_character_name()
            C = "\033[36m"; B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
            G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"
            print(f"  {B}📊 CUSTOM STATS:{RS} {char_name}")
            for stat_name, stat_data in stats.items():
                current = stat_data['current']
                max_val = stat_data.get('max')
                if max_val is not None:
                    bar_len = 20
                    pct = current / max_val if max_val > 0 else 0
                    fill = int(pct * bar_len)
                    bar_color = G if pct < 0.3 else Y if pct < 0.6 else R
                    bar = f"{bar_color}{'█' * fill}{DM}{'░' * (bar_len - fill)}{RS}"
                    print(f"  {stat_name:12s} {bar} {C}{int(current):>3}{RS}/{max_val}")
                else:
                    print(f"  {stat_name}: {C}{current}{RS}")

        elif args.action == 'rate':
            value_str = ' '.join(args.value)
            result = engine.set_rate_modifier(args.stat, value_str)
            C = "\033[36m"; Y = "\033[33m"; RS = "\033[0m"
            def _fmt_r(v):
                if v == 0: return "0"
                if abs(v) < 0.1: return f"{v*24:+.1f}/d"
                return f"{v:+.1f}/h"
            print(f"  📊 {args.stat} rate: {_fmt_r(result['old_modifier'])} → {C}{_fmt_r(result['new_modifier'])}{RS}")

        elif args.action == 'rates':
            engine.show_rates()

        elif args.action == 'effect':
            if args.effect_action == 'add':
                effects = []
                for i, stat in enumerate(args.stat):
                    eff = {'stat': stat}
                    if i < len(args.rate_bonus):
                        eff['rate_bonus'] = args.rate_bonus[i]
                    if i < len(args.per_hour):
                        eff['per_hour'] = args.per_hour[i]
                    if i < len(args.instant):
                        eff['instant'] = args.instant[i]
                    effects.append(eff)
                engine.add_effect(args.name, effects, args.duration, stackable=args.stackable)
            elif args.effect_action == 'remove':
                engine.remove_effect(args.name)
            else:
                effect_parser.print_help()

        elif args.action == 'effects':
            engine.list_effects()

    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
