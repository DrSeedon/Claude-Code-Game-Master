#!/usr/bin/env python3
"""
Survival Engine — standalone module for custom stats time effects.

Imports CORE's PlayerManager and JsonOperations. CORE has zero knowledge of this module.
DM (Claude) calls this via dm-survival.sh after time advances.
"""

import argparse
import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.json_ops import JsonOperations
from lib.player_manager import PlayerManager
from lib.campaign_manager import CampaignManager


class SurvivalEngine:
    """Apply time-based effects to custom stats and check stat consequences."""

    def __init__(self, world_state_dir: str = "world-state"):
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign.")

        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.player_mgr = PlayerManager(str(self.campaign_dir.parent.parent))

    def _normalize_custom_stats(self, char: dict) -> dict:
        """Normalize custom_stats: convert {value, min, max} → {current, min, max}"""
        for stat_data in char.get('custom_stats', {}).values():
            if isinstance(stat_data, dict) and 'current' not in stat_data and 'value' in stat_data:
                stat_data['current'] = stat_data['value']
        return char

    def tick(self, elapsed_hours: float, sleeping: bool = False) -> dict:
        """
        Main entry point. Apply time effects + check stat consequences.

        Returns dict with stat_changes, stat_consequences lists.
        """
        campaign = self.json_ops.load_json("campaign-overview.json")
        time_effects = campaign.get('campaign_rules', {}).get('time_effects', {})

        if not time_effects.get('enabled'):
            print("[SKIP] Time effects not enabled for this campaign")
            return {'stat_changes': [], 'stat_consequences': []}

        char_name = campaign.get('current_character')
        if not char_name:
            print("[SKIP] No active character")
            return {'stat_changes': [], 'stat_consequences': []}

        stat_changes = self._apply_time_effects(elapsed_hours, time_effects, char_name, sleeping=sleeping)
        stat_consequences = self._check_stat_consequences(elapsed_hours, time_effects, char_name)

        self._print_report(stat_changes, stat_consequences)

        return {
            'stat_changes': stat_changes,
            'stat_consequences': stat_consequences
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

        char = self._normalize_custom_stats(char)
        custom_stats = char.get('custom_stats', {})
        if not custom_stats:
            print(f"[INFO] {char_name} has no custom stats")
            return {}

        print(f"Custom Stats for {char_name}:")
        for stat_name, stat_data in custom_stats.items():
            current = stat_data['current']
            max_val = stat_data.get('max')
            if max_val is not None:
                bar_len = 20
                fill = int((current / max_val) * bar_len)
                bar = '█' * fill + '░' * (bar_len - fill)
                print(f"  {stat_name}: {bar} {current}/{max_val}")
            else:
                print(f"  {stat_name}: {current}")

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

        char_data = self.json_ops.load_json("character.json")
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
                        cur = cs.get('current', cs.get('value', 0))
                        new_val = cur + amount
                        cs_max = cs.get('max')
                        cs_min = cs.get('min', 0)
                        if cs_max is not None:
                            new_val = min(new_val, cs_max)
                        if cs_min is not None:
                            new_val = max(new_val, cs_min)
                        cs['value'] = round(new_val, 2)
                        cs.pop('current', None)

        if has_instant_hp:
            fresh = self.json_ops.load_json("character.json")
            fresh['active_effects'] = char_data['active_effects']
            fresh['custom_stats'] = char_data.get('custom_stats', fresh.get('custom_stats', {}))
            char_data = fresh

        self.json_ops.save_json("character.json", char_data)
        print(f"[EFFECT] Added '{name}' for {duration_hours}h (stackable={stackable})")
        return effect_entry

    def remove_effect(self, name: str, char_name: str = None) -> int:
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self.json_ops.load_json("character.json")
        active_effects = char_data.get('active_effects', [])
        before = len(active_effects)
        char_data['active_effects'] = [e for e in active_effects if e['name'] != name]
        removed = before - len(char_data['active_effects'])
        self.json_ops.save_json("character.json", char_data)
        print(f"[EFFECT] Removed {removed} effect(s) named '{name}'")
        return removed

    def list_effects(self, char_name: str = None) -> list:
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self.json_ops.load_json("character.json")
        active_effects = char_data.get('active_effects', [])

        if not active_effects:
            print("[INFO] No active effects")
            return []

        print(f"\nActive Effects:")
        print(f"  {'Name':<20} {'Remaining':>10} {'Duration':>10} {'Details'}")
        print(f"  {'─'*20} {'─'*10} {'─'*10} {'─'*30}")
        for eff in active_effects:
            details = []
            for e in eff['effects']:
                parts = [e['stat']]
                if 'rate_bonus' in e:
                    parts.append(f"rate {e['rate_bonus']:+g}")
                if 'per_hour' in e:
                    parts.append(f"{e['per_hour']:+g}/h")
                if 'instant' in e:
                    parts.append(f"instant {e['instant']:+g}")
                details.append(' '.join(parts))
            detail_str = ', '.join(details)
            print(f"  {eff['name']:<20} {eff['remaining_hours']:>9.1f}h {eff['duration_hours']:>9.1f}h {detail_str}")

        return active_effects

    def set_rate_modifier(self, stat: str, value: str, char_name: str = None) -> dict:
        """Set rate_modifier for a stat. value: '+N', '-N', 'set N', 'reset'."""
        if char_name is None:
            char_name = self._get_active_character_name()

        char_data = self.json_ops.load_json("character.json")
        cs = char_data.get('custom_stats', {}).get(stat)
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
        self.json_ops.save_json("character.json", char_data)
        return {'stat': stat, 'old_modifier': old_mod, 'new_modifier': new_mod}

    def show_rates(self, char_name: str = None) -> list:
        """Show effective rates for all stats. Returns list of rate info dicts."""
        if char_name is None:
            char_name = self._get_active_character_name()

        campaign = self.json_ops.load_json("campaign-overview.json")
        time_effects = campaign.get('campaign_rules', {}).get('time_effects', {})
        rules = time_effects.get('rules', [])
        if not rules:
            effects_per_hour = time_effects.get('effects_per_hour', {})
            if effects_per_hour:
                rules = [{'stat': s, 'per_hour': c} for s, c in effects_per_hour.items()]

        char_data = self.json_ops.load_json("character.json")
        char = self.player_mgr.get_player(char_name)
        if char:
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

        print(f"\nRate Table:")
        print(f"  {'Stat':<12} {'Base':>6} {'Mod':>6} {'Effects':>8} {'Blocked':>8} {'Effective':>10}")
        print(f"  {'─'*12} {'─'*6} {'─'*6} {'─'*8} {'─'*8} {'─'*10}")
        for r in rows:
            bl = 'YES' if r['blocked'] else ''
            eff_str = f"{r['effect_bonus']:>+8.1f}" if r['effect_bonus'] != 0 else f"{'':>8}"
            print(f"  {r['stat']:<12} {r['base']:>+6.1f} {r['modifier']:>+6.1f} {eff_str} {bl:>8} {r['effective']:>+10.1f}")

        return rows

    def _apply_time_effects(self, elapsed_hours: float, time_effects: dict, char_name: str, sleeping: bool = False) -> list:
        """Apply per-tick stat changes based on time_effects rules."""
        char = self.player_mgr.get_player(char_name)
        if not char:
            return []
        char = self._normalize_custom_stats(char)

        rules = time_effects.get('rules', [])
        if not rules:
            effects_per_hour = time_effects.get('effects_per_hour', {})
            if effects_per_hour:
                rules = [{'stat': stat, 'per_hour': change} for stat, change in effects_per_hour.items()]

        if not rules:
            return []

        char_data = self.json_ops.load_json("character.json")
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

                if stat == 'sleep' and sleeping:
                    change_per_hour = rule.get('sleep_restore_per_hour', 12.5)

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
                        char_data = self.json_ops.load_json("character.json")
                        cs_entry = char_data.get('custom_stats', {}).get(stat)
                        if cs_entry:
                            cs_max = cs_entry.get('max')
                            cs_min = cs_entry.get('min', 0)
                            cur = cs_entry.get('current', cs_entry.get('value', 0))
                            new_val = cur + diff
                            if cs_max is not None:
                                new_val = min(new_val, cs_max)
                            if cs_min is not None:
                                new_val = max(new_val, cs_min)
                            new_val = round(new_val, 2)
                            cs_entry['value'] = new_val
                            cs_entry.pop('current', None)
                            self.json_ops.save_json("character.json", char_data)
                            changes.append({'stat': stat, 'old': old_val, 'new': new_val, 'change': diff})

        if active_effects:
            char_data = self.json_ops.load_json("character.json")
            char_data['active_effects'] = [e for e in active_effects if e.get('remaining_hours', 0) > 0]
            self.json_ops.save_json("character.json", char_data)

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
        if stat_changes:
            print("\nSurvival Effects:")
            for change in stat_changes:
                sign = '+' if change['change'] > 0 else ''
                print(f"  {change['stat']}: {change['old']} → {change['new']} ({sign}{change['change']:.1f})")

        if stat_consequences:
            print("\nStat Consequences:")
            for sc in stat_consequences:
                print(f"  ⚠️ {sc['name']}: {sc['message']}")

        if not stat_changes and not stat_consequences:
            print("[OK] No survival effects triggered")

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

        char = self.player_mgr.get_player(name)
        if not char:
            raise RuntimeError(f"Character '{name}' not found")

        self._normalize_custom_stats(char)
        custom_stats = char.get('custom_stats', {})
        if stat and stat not in custom_stats:
            raise RuntimeError(f"Custom stat '{stat}' not found for {name}")

        if stat:
            return {stat: custom_stats[stat]}
        return custom_stats

    def modify_custom_stat(self, name: str = None, stat: str = None, amount: float = 0) -> dict:
        """Modify custom stat. Clamp to min/max. If name is None, uses active character."""
        if name is None:
            name = self._get_active_character_name()

        char = self.json_ops.load_json("character.json")
        cs = char.get('custom_stats', {}).get(stat)
        if cs is None:
            raise RuntimeError(f"Custom stat '{stat}' not found for {name}")

        old_val = cs.get('current', cs.get('value', 0))
        new_val = old_val + amount
        cs_max = cs.get('max')
        cs_min = cs.get('min', 0)
        if cs_max is not None:
            new_val = min(new_val, cs_max)
        if cs_min is not None:
            new_val = max(new_val, cs_min)
        new_val = round(new_val, 2)
        cs['value'] = new_val
        cs.pop('current', None)
        self.json_ops.save_json("character.json", char)
        return {'success': True, 'old_value': old_val, 'new_value': new_val}

    def list_custom_stats(self, name: str = None) -> dict:
        """List all custom stats for character."""
        if name is None:
            name = self._get_active_character_name()

        char = self.player_mgr.get_player(name)
        if not char:
            raise RuntimeError(f"Character '{name}' not found")

        self._normalize_custom_stats(char)
        return char.get('custom_stats', {})

    def advance_time(self, time_of_day: str, date: str, elapsed_hours: float = 0,
                     precise_time: str = None, sleeping: bool = False) -> bool:
        """
        Full time advance with survival mechanics.

        1. If precise_time given, auto-calculate elapsed from previous precise_time
        2. Update campaign-overview.json with time_of_day, date, precise_time
        3. If elapsed_hours > 0, call self.tick(elapsed_hours, sleeping) for stat effects
        4. Check timed consequences (_check_time_consequences)
        5. Print report
        """
        campaign = self.json_ops.load_json("campaign-overview.json")

        auto_elapsed = 0
        if precise_time:
            previous_time = campaign.get('time', {}).get('precise_time')
            previous_date = campaign.get('time', {}).get('date')
            if previous_time and previous_date:
                auto_elapsed = self._calculate_elapsed_hours(previous_time, precise_time, previous_date, date)
            elapsed_hours = auto_elapsed

        campaign.setdefault('time', {})
        campaign['time']['time_of_day'] = time_of_day
        campaign['time']['date'] = date
        if precise_time:
            campaign['time']['precise_time'] = precise_time

        self.json_ops.save_json("campaign-overview.json", campaign)

        stat_changes = []
        stat_consequences = []
        timed_consequences = []

        if elapsed_hours > 0:
            result = self.tick(elapsed_hours, sleeping=sleeping)
            stat_changes = result['stat_changes']
            stat_consequences = result['stat_consequences']

            timed_consequences = self._check_time_consequences(elapsed_hours)

        print(f"\n[SUCCESS] Time updated to: {time_of_day} ({precise_time or 'no precise time'}), {date}")
        if elapsed_hours > 0:
            print(f"Elapsed: {elapsed_hours:.2f} hours")

        if timed_consequences:
            print("\nTriggered Events:")
            for tc in timed_consequences:
                print(f"  ⚠️ {tc['event']}")

        return True

    def _calculate_elapsed_hours(self, prev_time: str, new_time: str, prev_date: str, new_date: str) -> float:
        """Calculate elapsed hours between two precise times and dates."""
        def parse_time(t: str) -> float:
            parts = t.split(':')
            return float(parts[0]) + float(parts[1]) / 60

        prev_hours = parse_time(prev_time)
        new_hours = parse_time(new_time)

        date_diff = 0
        if new_date != prev_date:
            try:
                prev_day = int(prev_date.split()[0].rstrip('stndrdth'))
                new_day = int(new_date.split()[0].rstrip('stndrdth'))
                date_diff = (new_day - prev_day) * 24
            except (ValueError, IndexError):
                date_diff = 0

        return date_diff + (new_hours - prev_hours)

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

    list_parser = subparsers.add_parser('custom-stats-list', help='List all custom stats')
    list_parser.add_argument('name', nargs='?', help='Character name (optional, auto-detects)')

    time_parser = subparsers.add_parser('time', help='Advance time with survival effects')
    time_parser.add_argument('time_of_day', help='Time of day label (Morning, Afternoon, etc.)')
    time_parser.add_argument('date', help='Date string')
    time_parser.add_argument('--elapsed', type=float, default=0, help='Hours elapsed')
    time_parser.add_argument('--precise-time', help='HH:MM format for auto-elapsed calculation')
    time_parser.add_argument('--sleeping', action='store_true', help='Character is sleeping')

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
                    print(f"[SUCCESS] {stat}: {result['old_value']} → {result['new_value']} ({amount:+.1f})")
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
            print(f"Custom Stats for {char_name}:")
            for stat_name, stat_data in stats.items():
                current = stat_data['current']
                max_val = stat_data.get('max')
                if max_val is not None:
                    print(f"  {stat_name}: {current}/{max_val}")
                else:
                    print(f"  {stat_name}: {current}")

        elif args.action == 'rate':
            value_str = ' '.join(args.value)
            result = engine.set_rate_modifier(args.stat, value_str)
            print(f"[SUCCESS] {args.stat} rate modifier: {result['old_modifier']:+.1f} → {result['new_modifier']:+.1f}")

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

        elif args.action == 'time':
            engine.advance_time(
                time_of_day=args.time_of_day,
                date=args.date,
                elapsed_hours=args.elapsed,
                precise_time=args.precise_time,
                sleeping=args.sleeping
            )

    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
