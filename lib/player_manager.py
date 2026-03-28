#!/usr/bin/env python3
"""
Player character management module for DM tools
Handles PC operations: XP, HP, level progression, and character data
"""

import sys
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

# Add lib directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from entity_manager import EntityManager
from currency import load_config, format_money, format_delta, parse_money, migrate_gold
from colors import tag_success, tag_error, tag_warning
from world_graph import WorldGraph


class PlayerManager(EntityManager):
    """Manage player character operations. Inherits from EntityManager for common functionality."""

    # D&D 5e XP thresholds for levels 1-20
    XP_THRESHOLDS = [
        0,       # Level 1
        300,     # Level 2
        900,     # Level 3
        2700,    # Level 4
        6500,    # Level 5
        14000,   # Level 6
        23000,   # Level 7
        34000,   # Level 8
        48000,   # Level 9
        64000,   # Level 10
        85000,   # Level 11
        100000,  # Level 12
        120000,  # Level 13
        140000,  # Level 14
        165000,  # Level 15
        195000,  # Level 16
        225000,  # Level 17
        265000,  # Level 18
        305000,  # Level 19
        355000,  # Level 20
    ]

    def __init__(self, world_state_dir: Optional[str] = None, require_active_campaign: bool = True):
        super().__init__(world_state_dir, require_active_campaign)

        self.world_state_dir = self.campaign_dir
        self.campaign_file = "campaign-overview.json"
        self._wg = WorldGraph(str(self.campaign_dir))

    def _load_character(self, name: Optional[str] = None) -> Optional[Dict]:
        """Load character data from WorldGraph player node."""
        node = self._wg.get_node("player:active")
        if node:
            merged = dict(node.get("data", {}))
            merged["name"] = node.get("name", merged.get("name", "Player"))
            return merged
        return None

    def _save_character(self, name: str, data: Dict) -> bool:
        """Save character data to WorldGraph player node."""
        char_name = data.pop("name", name)
        self._wg.update_node("player:active", {"name": char_name, "data": data})
        data["name"] = char_name
        return True

    def _normalize_xp(self, char: Dict) -> Dict:
        """Normalize XP to object format {current, next_level}"""
        xp = char.get('xp', 0)
        level = char.get('level', 1)

        if isinstance(xp, int):
            # Old format: plain integer
            next_threshold = self.XP_THRESHOLDS[level] if level < 20 else xp
            char['xp'] = {'current': xp, 'next_level': next_threshold}
        elif not isinstance(xp, dict):
            # Invalid format, reset
            char['xp'] = {'current': 0, 'next_level': self.XP_THRESHOLDS[1]}

        return char

    def get_player(self, name: Optional[str] = None) -> Optional[Dict]:
        """Get full player character data"""
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return None
        return char

    def list_players(self) -> List[str]:
        """List all player character IDs"""
        char = self._load_character()
        if char:
            return [char.get('name', 'character').lower().replace(' ', '-')]
        return []

    def show_player(self, name: str) -> Optional[str]:
        """Get formatted player summary"""
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return None

        hp = char.get('hp', {})
        currency_config = load_config(self.campaign_dir)
        raw_money = char.get('money', None)
        if raw_money is None:
            raw_money = migrate_gold(char.get('gold', 0), currency_config)
        summary = f"{char.get('name', name)} - {char.get('race', '?')} {char.get('class', '?')} Level {char.get('level', 1)} (HP: {hp.get('current', 0)}/{hp.get('max', 0)}, Gold: {format_money(raw_money, currency_config)})"
        conditions = char.get('conditions', [])
        if conditions:
            summary += f" | Conditions: {', '.join(conditions)}"
        return summary

    def show_all_players(self) -> List[str]:
        """Get summaries for all players"""
        char = self._load_character()
        if not char:
            return []
        currency_config = load_config(self.campaign_dir)
        hp = char.get('hp', {})
        raw_money = char.get('money', None)
        if raw_money is None:
            raw_money = migrate_gold(char.get('gold', 0), currency_config)
        return [
            f"{char.get('name', 'Unknown')} - {char.get('race', '?')} {char.get('class', '?')} Level {char.get('level', 1)} (HP: {hp.get('current', 0)}/{hp.get('max', 0)}, Gold: {format_money(raw_money, currency_config)})"
        ]

    def set_current_player(self, name: str) -> bool:
        """Set character as current active PC in campaign"""
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return False

        # Get actual name from character file
        actual_name = char.get('name', name)

        if self.json_ops.update_json(self.campaign_file, {'current_character': actual_name}):
            print(tag_success(f"Set current character to: {actual_name}"))
            return True
        return False

    def award_xp(self, name: str, amount: int) -> Dict[str, Any]:
        """
        Award XP to character and check for level up
        Returns dict with xp_gained, new_total, level_up, new_level
        """
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return {'success': False}

        # Normalize XP structure
        char = self._normalize_xp(char)

        # Add XP
        char['xp']['current'] += amount
        current_xp = char['xp']['current']
        current_level = char.get('level', 1)

        # Check for level up
        new_level = current_level
        while new_level < 20 and current_xp >= self.XP_THRESHOLDS[new_level]:
            new_level += 1

        leveled_up = new_level > current_level
        if leveled_up:
            char['level'] = new_level

        # Update next level threshold
        next_threshold = self.XP_THRESHOLDS[new_level] if new_level < 20 else current_xp
        char['xp']['next_level'] = next_threshold

        # Save character
        if not self._save_character(name, char):
            return {'success': False}

        result = {
            'success': True,
            'name': char.get('name', name),
            'xp_gained': amount,
            'current_xp': current_xp,
            'next_level_xp': next_threshold if new_level < 20 else 'MAX',
            'level_up': leveled_up,
            'old_level': current_level,
            'new_level': new_level
        }

        # Print result
        if leveled_up:
            print(f"LEVEL_UP {char.get('name', name)} gained {amount} XP and leveled up to Level {new_level}!")
            print(f"XP: {current_xp}/{next_threshold if new_level < 20 else 'MAX'}")
        else:
            print(f"XP_GAIN {char.get('name', name)} gained {amount} XP!")
            print(f"XP: {current_xp}/{next_threshold if new_level < 20 else 'MAX'}")

        return result

    def get_xp_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get XP and level status for character"""
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return None

        # Normalize XP structure
        char = self._normalize_xp(char)
        self._save_character(name, char)

        current_xp = char['xp']['current']
        current_level = char.get('level', 1)
        next_level_xp = char['xp']['next_level']

        # Check if ready to level up
        ready_to_level = current_xp >= next_level_xp and current_level < 20
        remaining = next_level_xp - current_xp if not ready_to_level else 0

        char_name = char.get('name', name)
        print(f"{char_name} - Level {current_level}")
        print(f"XP: {current_xp}/{next_level_xp}")

        if ready_to_level:
            print("READY_TO_LEVEL_UP")
        else:
            print(f"Next level in: {remaining} XP")

        return {
            'name': char_name,
            'level': current_level,
            'current_xp': current_xp,
            'next_level_xp': next_level_xp,
            'ready_to_level': ready_to_level,
            'xp_remaining': remaining
        }

    def modify_hp(self, name: str, amount: int) -> Dict[str, Any]:
        """
        Modify character HP (positive = heal, negative = damage)
        Returns dict with HP status info
        """
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return {'success': False}

        hp = char.get('hp', {})
        current_hp = hp.get('current', 0)
        max_hp = hp.get('max', 0)

        # Apply change and clamp between 0 and max
        new_hp = max(0, min(current_hp + amount, max_hp))
        char['hp']['current'] = new_hp

        # Save character
        if not self._save_character(name, char):
            return {'success': False}

        char_name = char.get('name', name)

        # Determine status
        if amount < 0:
            print(f"DAMAGE {char_name} took {abs(amount)} damage!")
        else:
            print(f"HEAL {char_name} healed {amount} HP!")

        print(f"HP: {new_hp}/{max_hp}")

        if new_hp == 0:
            print("STATUS: UNCONSCIOUS")
        elif new_hp <= max_hp // 4:
            print("STATUS: BLOODIED")

        return {
            'success': True,
            'name': char_name,
            'hp_change': amount,
            'current_hp': new_hp,
            'max_hp': max_hp,
            'unconscious': new_hp == 0,
            'bloodied': 0 < new_hp <= max_hp // 4
        }

    def set_hp_max(self, name: str, amount: int) -> Dict[str, Any]:
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return {'success': False}

        hp = char.get('hp', {})
        old_max = hp.get('max', 0)
        new_max = old_max + amount
        if new_max < 1:
            new_max = 1
        char['hp']['max'] = new_max
        if char['hp']['current'] > new_max:
            char['hp']['current'] = new_max
        if amount > 0:
            char['hp']['current'] = min(char['hp']['current'] + amount, new_max)

        if not self._save_character(name, char):
            return {'success': False}

        char_name = char.get('name', name)
        sign = f"+{amount}" if amount > 0 else str(amount)
        print(f"HP_MAX {char_name}: {old_max} → {new_max} ({sign})")
        print(f"HP: {char['hp']['current']}/{new_max}")
        return {'success': True, 'old_max': old_max, 'new_max': new_max, 'current_hp': char['hp']['current']}

    def modify_money(self, name: str, amount=None) -> Dict[str, Any]:
        """
        Modify character money or show current balance if no amount given.
        amount can be int (base units) or string like "2g 5s" or "+10" or "-50".
        Returns dict with money status info.
        """
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return {'success': False}

        char_name = char.get('name', name)
        config = load_config(self.campaign_dir)

        raw_money = char.get('money', None)
        if raw_money is None:
            raw_money = migrate_gold(char.get('gold', 0), config)
            if not isinstance(raw_money, int):
                raw_money = 0
        current_money = raw_money

        if amount is None:
            print(f"{char_name}: {format_money(current_money, config)}")
            return {
                'success': True,
                'name': char_name,
                'money': current_money
            }

        if isinstance(amount, str):
            try:
                delta = parse_money(amount, config)
                if amount.lstrip().startswith('-'):
                    delta = -abs(delta)
            except ValueError:
                print(tag_error(f"Invalid money amount: {amount}"))
                return {'success': False}
        else:
            delta = int(amount)

        new_money = current_money + delta
        if new_money < 0:
            print(tag_warning(f"{char_name} only has {format_money(current_money, config)} (tried to spend {format_money(abs(delta), config)}). Set to 0."))
            new_money = 0
        char['money'] = new_money
        char.pop('gold', None)

        if not self._save_character(name, char):
            return {'success': False}

        if delta > 0:
            print(f"GOLD_GAINED {char_name} gained {format_delta(delta, config)}!")
        elif delta < 0:
            print(f"GOLD_SPENT {char_name} spent {format_money(abs(delta), config)}!")
        else:
            print(f"{char_name} money unchanged.")

        print(f"Gold: {format_money(new_money, config)}")

        return {
            'success': True,
            'name': char_name,
            'gold_change': delta,
            'current_gold': new_money
        }

    def modify_gold(self, name: str, amount=None) -> Dict[str, Any]:
        return self.modify_money(name, amount)

    def modify_condition(self, name: str, action: str, condition: Optional[str] = None) -> Dict[str, Any]:
        """
        Add, remove, or list conditions on a character
        action: 'add', 'remove', or 'list'
        """
        char = self._load_character(name)
        if not char:
            print(tag_error(f"Character '{name}' not found"))
            return {'success': False}

        char_name = char.get('name', name)

        # Auto-init conditions list if missing
        if 'conditions' not in char:
            char['conditions'] = []

        conditions = char['conditions']

        if action == 'list':
            print(f"{char_name}'s Conditions:")
            if conditions:
                for c in conditions:
                    print(f"  - {c}")
            else:
                print("  (none)")
            return {'success': True, 'name': char_name, 'conditions': conditions}

        if not condition:
            print(tag_error(f"Condition name required for {action}"))
            return {'success': False}

        if action == 'add':
            # Case-insensitive dedup
            if condition.lower() not in [c.lower() for c in conditions]:
                conditions.append(condition)
                char['conditions'] = conditions
                if not self._save_character(name, char):
                    return {'success': False}
                print(f"CONDITION_ADDED {char_name}: {condition}")
            else:
                print(f"{char_name} already has condition: {condition}")
            return {'success': True, 'name': char_name, 'conditions': conditions}

        elif action == 'remove':
            # Case-insensitive match
            found_idx = None
            for idx, c in enumerate(conditions):
                if c.lower() == condition.lower():
                    found_idx = idx
                    break
            if found_idx is None:
                print(tag_error(f"Condition '{condition}' not found on {char_name}"))
                return {'success': False}
            removed = conditions.pop(found_idx)
            char['conditions'] = conditions
            if not self._save_character(name, char):
                return {'success': False}
            print(f"CONDITION_REMOVED {char_name}: {removed}")
            return {'success': True, 'name': char_name, 'conditions': conditions}

        else:
            print(tag_error(f"Unknown condition action: {action}"))
            return {'success': False}


def main():
    """CLI interface for player management"""
    import argparse

    parser = argparse.ArgumentParser(description='Player character management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Show player(s)
    show_parser = subparsers.add_parser('show', help='Show player(s)')
    show_parser.add_argument('name', nargs='?', help='Character name (optional, shows all if omitted)')

    # List players
    subparsers.add_parser('list', help='List all player IDs')

    # Set current player
    set_parser = subparsers.add_parser('set', help='Set current active character')
    set_parser.add_argument('name', help='Character name')

    # Award XP
    xp_parser = subparsers.add_parser('xp', help='Award XP to character')
    xp_parser.add_argument('name', help='Character name')
    xp_parser.add_argument('amount', help='XP amount (can include + prefix)')

    # Check level status
    level_parser = subparsers.add_parser('level-check', help='Check XP and level status')
    level_parser.add_argument('name', help='Character name')

    # Modify HP
    hp_parser = subparsers.add_parser('hp', help='Modify character HP')
    hp_parser.add_argument('name', help='Character name')
    hp_parser.add_argument('amount', help='HP change (+5 to heal, -3 for damage)')

    # Modify HP max
    hpmax_parser = subparsers.add_parser('hp-max', help='Modify character max HP')
    hpmax_parser.add_argument('name', help='Character name')
    hpmax_parser.add_argument('amount', help='Max HP change (+6 for level up, -5 for curse)')

    # Get full character JSON
    get_parser = subparsers.add_parser('get', help='Get full character JSON')
    get_parser.add_argument('name', help='Character name')

    # Modify money (subcommand still called 'gold' for backward compat)
    gold_parser = subparsers.add_parser('gold', help='Modify or show character money')
    gold_parser.add_argument('name', help='Character name')
    gold_parser.add_argument('amount', nargs='?', help='Money change: +50 (base units), -10, "2g 5s", "-3gp". Omit to show current.')

    # Manage conditions
    cond_parser = subparsers.add_parser('condition', help='Manage character conditions')
    cond_parser.add_argument('name', help='Character name')
    cond_parser.add_argument('cond_action', choices=['add', 'remove', 'list'], help='Action to perform')
    cond_parser.add_argument('condition', nargs='?', help='Condition name (required for add/remove)')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    manager = PlayerManager()

    if args.action == 'show':
        if args.name:
            result = manager.show_player(args.name)
            if result:
                print(result)
            else:
                sys.exit(1)
        else:
            summaries = manager.show_all_players()
            for s in summaries:
                print(s)

    elif args.action == 'list':
        players = manager.list_players()
        for p in players:
            print(p)

    elif args.action == 'set':
        if not manager.set_current_player(args.name):
            sys.exit(1)

    elif args.action == 'xp':
        # Parse amount (handle +150 format)
        amount_str = args.amount.replace('+', '')
        try:
            amount = int(amount_str)
        except ValueError:
            print(tag_error(f"Invalid XP amount: {args.amount}"))
            sys.exit(1)

        result = manager.award_xp(args.name, amount)
        if not result.get('success'):
            sys.exit(1)

    elif args.action == 'level-check':
        if not manager.get_xp_status(args.name):
            sys.exit(1)

    elif args.action == 'hp':
        # Parse amount (handle +5 or -3 format)
        amount_str = args.amount
        try:
            if amount_str.startswith('+'):
                amount = int(amount_str[1:])
            else:
                amount = int(amount_str)
        except ValueError:
            print(tag_error(f"Invalid HP amount: {args.amount}"))
            sys.exit(1)

        result = manager.modify_hp(args.name, amount)
        if not result.get('success'):
            sys.exit(1)

    elif args.action == 'hp-max':
        amount_str = args.amount
        try:
            if amount_str.startswith('+'):
                amount = int(amount_str[1:])
            else:
                amount = int(amount_str)
        except ValueError:
            print(tag_error(f"Invalid HP max amount: {args.amount}"))
            sys.exit(1)
        result = manager.set_hp_max(args.name, amount)
        if not result.get('success'):
            sys.exit(1)

    elif args.action == 'get':
        char = manager.get_player(args.name)
        if char:
            print(json.dumps(char, indent=2, ensure_ascii=False))
        else:
            sys.exit(1)

    elif args.action == 'gold':
        amount = None
        if args.amount:
            amount_str = args.amount.strip()
            has_letters = any(c.isalpha() for c in amount_str)
            if has_letters:
                amount = amount_str
            else:
                try:
                    if amount_str.startswith('+'):
                        amount = int(amount_str[1:])
                    else:
                        amount = int(amount_str)
                except ValueError:
                    print(tag_error(f"Invalid money amount: {args.amount}"))
                    sys.exit(1)

        result = manager.modify_money(args.name, amount)
        if not result.get('success'):
            sys.exit(1)

    elif args.action == 'condition':
        result = manager.modify_condition(args.name, args.cond_action, args.condition)
        if not result.get('success'):
            sys.exit(1)


if __name__ == "__main__":
    main()
