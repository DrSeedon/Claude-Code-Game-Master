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

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
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

    def _apply_time_effects(self, elapsed_hours: float, time_effects: dict, char_name: str, sleeping: bool = False) -> list:
        """Apply per-tick stat changes based on time_effects rules."""
        char = self.player_mgr.get_player(char_name)
        if not char:
            return []

        rules = time_effects.get('rules', [])
        if not rules:
            effects_per_hour = time_effects.get('effects_per_hour', {})
            if effects_per_hour:
                rules = [{'stat': stat, 'per_hour': change} for stat, change in effects_per_hour.items()]

        if not rules:
            return []

        sim_char = copy.deepcopy(char)

        for _ in range(int(elapsed_hours)):
            for rule in rules:
                stat = rule['stat']
                change_per_hour = rule.get('per_hour', 0)

                if stat == 'sleep' and sleeping:
                    change_per_hour = rule.get('sleep_restore_per_hour', 12.5)

                condition = rule.get('condition')
                if condition and not self._check_rule_condition(condition, sim_char):
                    continue

                if abs(change_per_hour) < 0.001:
                    continue

                if stat == 'hp':
                    sim_char['hp']['current'] = max(0, min(
                        sim_char['hp']['current'] + int(change_per_hour),
                        sim_char['hp']['max']
                    ))
                else:
                    cs = sim_char.get('custom_stats', {}).get(stat)
                    if cs:
                        new_val = cs['current'] + change_per_hour
                        cs_max = cs.get('max')
                        cs_min = cs.get('min', 0)
                        if cs_max is not None:
                            new_val = min(new_val, cs_max)
                        if cs_min is not None:
                            new_val = max(new_val, cs_min)
                        cs['current'] = new_val

        changes = []
        for stat in set(r['stat'] for r in rules):
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
                        result = self.player_mgr.modify_custom_stat(name=char_name, stat=stat, amount=diff)
                        if result and result.get('success'):
                            changes.append({'stat': stat, 'old': result['old_value'], 'new': result['new_value'], 'change': diff})

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


def main():
    parser = argparse.ArgumentParser(description='Survival Stats Module')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    tick_parser = subparsers.add_parser('tick', help='Apply time effects')
    tick_parser.add_argument('--elapsed', type=float, required=True, help='Hours elapsed')
    tick_parser.add_argument('--sleeping', action='store_true', help='Character is sleeping')

    subparsers.add_parser('status', help='Show current custom stats')

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

    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
