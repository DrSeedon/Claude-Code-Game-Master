#!/usr/bin/env python3
"""
Unified Inventory Manager
Handles all character inventory/stats operations in atomic transactions
Inventory data stored in module-data/inventory-system.json
"""

import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from copy import deepcopy

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "infrastructure"))
from module_data import ModuleDataManager


ITEM_CATEGORIES = {
    "weapon": ["АК", "AK", "ПМ", "PM", "SVD", "СВД", "Glock", "нож", "knife",
               "rifle", "pistol", "shotgun", "обрез", "дробовик", "винтовк",
               "автомат", "пистолет", "ружь"],
    "ammo": ["патрон", "ammo", "mm", "мм", "калибр", "gauge",
             "x39", "x18", "x54", "x19", "x45"],
    "food": ["еда", "food", "тушён", "хлеб", "консерв", "колбас", "сухпай",
             "bread", "ration", "вода", "water"],
    "medicine": ["бинт", "аптечка", "медик", "антирад", "bandage", "medkit",
                 "medicine", "stim", "промедол", "антибиотик"],
    "artifact": ["артефакт", "artifact", "artefact"],
}


class InventoryManager:
    """Unified manager for character inventory, gold, HP, XP, and custom stats"""

    def __init__(self, campaign_path: Path):
        self.campaign_path = campaign_path
        self.character_file = campaign_path / "character.json"
        self.module_data_mgr = ModuleDataManager(campaign_path)
        self.character = self._load_character()
        self.inventory = self._load_inventory()
        self.changes_log = []

    def _load_character(self) -> Dict:
        """Load character.json + inject custom_stats from module-data"""
        if not self.character_file.exists():
            raise FileNotFoundError(f"Character file not found: {self.character_file}")

        with open(self.character_file, 'r', encoding='utf-8') as f:
            char = json.load(f)

        cs_data = self.module_data_mgr.load("custom-stats")
        if cs_data:
            char['custom_stats'] = cs_data.get('character_stats', {})
        return char

    def _save_character(self):
        """Save character.json (without inventory/custom_stats) + persist custom_stats to module-data"""
        custom_stats = self.character.pop('custom_stats', {})
        save_data = {k: v for k, v in self.character.items() if k != "inventory"}
        with open(self.character_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        if custom_stats:
            self.character['custom_stats'] = custom_stats
            cs_data = self.module_data_mgr.load("custom-stats") or {}
            cs_data['character_stats'] = custom_stats
            self.module_data_mgr.save("custom-stats", cs_data)

    def _load_inventory(self) -> Dict:
        """Load inventory from module-data/inventory-system.json"""
        data = self.module_data_mgr.load("inventory-system")
        if not data:
            return {"stackable": {}, "unique": []}
        return data

    def _save_inventory(self):
        """Save inventory to module-data/inventory-system.json"""
        self.module_data_mgr.save("inventory-system", self.inventory)

    def _migrate_old_format(self):
        """Migrate old equipment/inventory from character.json to module-data"""
        if "equipment" in self.character:
            print("[MIGRATION] Converting old equipment format...")

            backup_file = self.character_file.with_suffix('.json.backup')
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.character, f, indent=2, ensure_ascii=False)
            print(f"[BACKUP] Saved to {backup_file}")

            stackable = {}
            unique = []

            for item in self.character.get("equipment", []):
                if self._is_unique_item(item):
                    unique.append(item)
                else:
                    item_name, quantity = self._parse_item_quantity(item)
                    if item_name in stackable:
                        stackable[item_name] += quantity
                    else:
                        stackable[item_name] = quantity

            self.inventory = {"stackable": stackable, "unique": unique}
            self._save_inventory()

            del self.character["equipment"]
            if "inventory" in self.character:
                del self.character["inventory"]
            self._save_character()

            print(f"[SUCCESS] Migrated {len(stackable)} stackable + {len(unique)} unique items")

        elif "inventory" in self.character:
            print("[MIGRATION] Moving inventory from character.json to module-data...")

            self.inventory = self.character["inventory"]
            self._save_inventory()

            del self.character["inventory"]
            self._save_character()

            print("[SUCCESS] Inventory moved to module-data/inventory-system.json")

    def _is_unique_item(self, item: str) -> bool:
        """Determine if item should be in unique category"""
        if re.search(r'\(.*(?:AC|HP|PEN|PROT|d\d+|\+\d+).*\)', item):
            return True

        keywords = ['PDA', 'ПДА', 'quest', 'квест', 'artifact', 'артефакт',
                    'key', 'ключ', 'note', 'записка', 'data', 'данные',
                    'flash', 'флешка', 'document', 'документ']

        item_lower = item.lower()
        if any(kw in item_lower for kw in keywords):
            return True

        weapon_armor = ['АКМ', 'АК-74', 'ПМ', 'M4', 'SVD', 'shotgun', 'rifle',
                        'armor', 'броня', 'vest', 'жилет', 'exo', 'экзо']

        if any(wa in item for wa in weapon_armor):
            return True

        return False

    def _parse_item_quantity(self, item: str) -> Tuple[str, int]:
        """Parse item name and quantity from string"""
        match = re.search(r'^(.+?)\s*\((\d+)\s*(?:шт|шт\.|pieces?)?\)$', item)

        if match:
            return match.group(1).strip(), int(match.group(2))
        else:
            return item.strip(), 1

    def validate_transaction(self, operations: Dict) -> Tuple[bool, List[str]]:
        """
        Validate all operations before applying

        Returns: (is_valid, error_messages)
        """
        errors = []

        if 'gold' in operations:
            current_gold = self.character.get("gold", 0)
            new_gold = current_gold + operations['gold']
            if new_gold < 0:
                errors.append(f"Not enough gold: need {abs(operations['gold'])}₽, have {current_gold}₽")

        if 'hp' in operations:
            current_hp = self.character.get("hp", {}).get("current", 0)
            max_hp = self.character.get("hp", {}).get("max", 0)
            new_hp = current_hp + operations['hp']
            if new_hp < -max_hp:
                errors.append(f"HP would drop to {new_hp} (too low, character would be dead)")

        for item, quantity in operations.get('remove', {}).items():
            stackable = self.inventory.get("stackable", {})

            if item not in stackable:
                errors.append(f"Item '{item}' not found in inventory")
            elif stackable[item] < quantity:
                errors.append(f"Cannot remove {quantity}x {item} (only {stackable[item]} available)")

        for item in operations.get('remove_unique', []):
            unique = self.inventory.get("unique", [])

            found = False
            for unique_item in unique:
                if item.lower() in unique_item.lower():
                    found = True
                    break

            if not found:
                errors.append(f"Unique item '{item}' not found in inventory")

        for stat_name, change in operations.get('custom_stats', {}).items():
            custom_stats = self.character.get("custom_stats", {})

            if stat_name not in custom_stats:
                errors.append(f"Custom stat '{stat_name}' does not exist")
            else:
                stat = custom_stats[stat_name]
                current = stat.get("current", stat.get("value", 0))
                min_val = stat.get("min", 0)
                max_val = stat.get("max", 100)
                new_val = current + change

                if new_val < min_val:
                    errors.append(f"Custom stat '{stat_name}' would drop to {new_val} (min: {min_val})")
                elif max_val is not None and new_val > max_val:
                    errors.append(f"Custom stat '{stat_name}' would exceed {new_val} (max: {max_val})")

        return (len(errors) == 0, errors)

    def apply_transaction(self, operations: Dict, test_mode: bool = False):
        """
        Apply atomic transaction

        operations format:
        {
            "gold": +/-amount,
            "hp": +/-amount,
            "xp": +/-amount,
            "add": {"ItemName": quantity, ...},
            "remove": {"ItemName": quantity, ...},
            "set": {"ItemName": quantity, ...},
            "add_unique": ["Item1", "Item2"],
            "remove_unique": ["Item1"],
            "custom_stats": {"hunger": +/-amount, ...}
        }
        """
        is_valid, errors = self.validate_transaction(operations)

        if not is_valid:
            print("[ERROR] Transaction validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            print("\n[ROLLBACK] No changes applied", file=sys.stderr)
            return False

        if test_mode:
            print("=" * 68)
            print("  TEST MODE - VALIDATION PASSED")
            print("=" * 68)
            self._preview_changes(operations)
            print("\n[TEST] No actual changes applied")
            return True

        original_character = deepcopy(self.character)
        original_inventory = deepcopy(self.inventory)

        try:
            self.changes_log = []

            if 'gold' in operations:
                old = self.character.get("gold", 0)
                new = old + operations['gold']
                self.character["gold"] = new
                self.changes_log.append(("gold", old, new, operations['gold']))

            if 'hp' in operations:
                old = self.character["hp"]["current"]
                new = max(0, old + operations['hp'])
                max_hp = self.character["hp"]["max"]
                new = min(new, max_hp)
                self.character["hp"]["current"] = new
                self.changes_log.append(("hp", old, new, operations['hp']))

            if 'xp' in operations:
                old = self.character.get("xp", {}).get("current", 0)
                new = old + operations['xp']
                if "xp" not in self.character:
                    self.character["xp"] = {"current": 0, "next_level": 300}
                self.character["xp"]["current"] = new
                self.changes_log.append(("xp", old, new, operations['xp']))

            stackable = self.inventory.setdefault("stackable", {})

            for item, quantity in operations.get('add', {}).items():
                old = stackable.get(item, 0)
                stackable[item] = old + quantity
                self.changes_log.append(("add", item, old, old + quantity, quantity))

            for item, quantity in operations.get('remove', {}).items():
                old = stackable[item]
                new = old - quantity
                if new <= 0:
                    del stackable[item]
                    self.changes_log.append(("remove", item, old, 0, quantity))
                else:
                    stackable[item] = new
                    self.changes_log.append(("remove", item, old, new, quantity))

            for item, quantity in operations.get('set', {}).items():
                old = stackable.get(item, 0)
                stackable[item] = quantity
                self.changes_log.append(("set", item, old, quantity, quantity - old))

            unique = self.inventory.setdefault("unique", [])
            for item in operations.get('add_unique', []):
                if item not in unique:
                    unique.append(item)
                    self.changes_log.append(("add_unique", item, None, None, None))

            for item in operations.get('remove_unique', []):
                for unique_item in unique[:]:
                    if item.lower() in unique_item.lower():
                        unique.remove(unique_item)
                        self.changes_log.append(("remove_unique", unique_item, None, None, None))
                        break

            for stat_name, change in operations.get('custom_stats', {}).items():
                stat = self.character["custom_stats"][stat_name]
                key = "current" if "current" in stat else "value"
                old = stat[key]
                new = old + change

                min_val = stat.get("min", 0)
                max_val = stat.get("max")
                new = max(min_val, new)
                if max_val is not None:
                    new = min(max_val, new)

                stat[key] = new
                self.changes_log.append(("custom_stat", stat_name, old, new, change))

            self._save_character()
            self._save_inventory()

            self._print_changes_summary()

            return True

        except Exception as e:
            self.character = original_character
            self.inventory = original_inventory
            self._save_character()
            self._save_inventory()
            print(f"[ERROR] Transaction failed: {e}", file=sys.stderr)
            print("[ROLLBACK] Changes reverted", file=sys.stderr)
            return False

    def _preview_changes(self, operations: Dict):
        """Preview what would change (for test mode)"""
        print("\nWOULD APPLY:")

        if 'gold' in operations:
            current = self.character.get("gold", 0)
            change = operations['gold']
            new = current + change
            print(f"  Gold: {current}₽ → {new}₽ ({change:+d})")

        if 'hp' in operations:
            current = self.character["hp"]["current"]
            max_hp = self.character["hp"]["max"]
            change = operations['hp']
            new = max(0, min(max_hp, current + change))
            print(f"  HP: {current}/{max_hp} → {new}/{max_hp} ({change:+d})")

        if 'xp' in operations:
            current = self.character.get("xp", {}).get("current", 0)
            change = operations['xp']
            new = current + change
            print(f"  XP: {current} → {new} ({change:+d})")

        for item, qty in operations.get('add', {}).items():
            current = self.inventory.get("stackable", {}).get(item, 0)
            print(f"  + {item} x{qty} (total: {current} → {current + qty})")

        for item, qty in operations.get('remove', {}).items():
            current = self.inventory.get("stackable", {}).get(item, 0)
            print(f"  - {item} x{qty} (total: {current} → {current - qty})")

        for item in operations.get('add_unique', []):
            print(f"  + {item} [unique]")

        for item in operations.get('remove_unique', []):
            print(f"  - {item} [unique]")

        for stat, change in operations.get('custom_stats', {}).items():
            sd = self.character.get("custom_stats", {}).get(stat, {})
            current = sd.get("current", sd.get("value", 0))
            new = current + change
            print(f"  {stat}: {current} → {new} ({change:+d})")

    def _print_changes_summary(self):
        """Print summary of applied changes"""
        print("=" * 68)
        print(f"  INVENTORY UPDATE: {self.character.get('name', 'Character')}")
        print("=" * 68)

        stat_changes = [entry for entry in self.changes_log
                        if entry[0] in ("gold", "hp", "xp", "custom_stat")]

        if stat_changes:
            print("\nCHANGES:")
            for entry in stat_changes:
                op = entry[0]
                if op == "gold":
                    old, new, delta = entry[1:4]
                    print(f"  Gold:     {old}₽ → {new}₽ ({delta:+d})")
                elif op == "hp":
                    old, new, delta = entry[1:4]
                    max_hp = self.character["hp"]["max"]
                    print(f"  HP:       {old}/{max_hp} → {new}/{max_hp} ({delta:+d})")
                elif op == "xp":
                    old, new, delta = entry[1:4]
                    print(f"  XP:       {old} → {new} ({delta:+d})")
                elif op == "custom_stat":
                    stat_name, old, new, delta = entry[1:5]
                    print(f"  {stat_name.capitalize()}: {old} → {new} ({delta:+d})")

        adds = [data for op, *data in self.changes_log if op == "add"]
        if adds:
            print("\nITEMS ADDED:")
            for item, old, new, qty in adds:
                print(f"  + {item} x{qty} (total: {new})")

        removes = [data for op, *data in self.changes_log if op == "remove"]
        if removes:
            print("\nITEMS REMOVED:")
            for item, old, new, qty in removes:
                if new == 0:
                    print(f"  - {item} x{qty} (depleted)")
                else:
                    print(f"  - {item} x{qty} (total: {old} → {new})")

        unique_adds = [data for op, *data in self.changes_log if op == "add_unique"]
        if unique_adds:
            print("\nUNIQUE ITEMS ADDED:")
            for item, *_ in unique_adds:
                print(f"  + {item}")

        unique_removes = [data for op, *data in self.changes_log if op == "remove_unique"]
        if unique_removes:
            print("\nUNIQUE ITEMS REMOVED:")
            for item, *_ in unique_removes:
                print(f"  - {item}")

        print("\n" + "=" * 68)
        print("[SUCCESS] Transaction completed")
        print("=" * 68)

    def _categorize_item(self, item_name: str) -> str:
        """Return category for an item based on keyword matching"""
        item_lower = item_name.lower()
        for category, keywords in ITEM_CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in item_lower:
                    return category
        return "misc"

    def transfer_to(self, target_name: str, items: Dict[str, int],
                    unique_items: List[str], test_mode: bool = False) -> bool:
        """Remove items from inventory as a transfer to target_name"""
        operations = {}

        if items:
            operations['remove'] = items
        if unique_items:
            operations['remove_unique'] = unique_items

        if not operations:
            print("[ERROR] No items specified for transfer", file=sys.stderr)
            return False

        is_valid, errors = self.validate_transaction(operations)
        if not is_valid:
            print("[ERROR] Transfer validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return False

        if test_mode:
            print("=" * 68)
            print(f"  TEST MODE — TRANSFER TO: {target_name}")
            print("=" * 68)
            self._preview_changes(operations)
            print("\n[TEST] No actual changes applied")
            return True

        success = self.apply_transaction(operations)
        if success:
            print(f"\n[TRANSFER] Items given to {target_name}:")
            for item, qty in items.items():
                print(f"  → {qty}x {item}")
            for item in unique_items:
                print(f"  → {item} [unique]")

        return success

    def show_inventory(self, category: Optional[str] = None):
        """Display full inventory, optionally filtered by category"""
        char = self.character
        name = char.get("name", "Character")
        gold = char.get("gold", 0)
        hp_cur = char.get("hp", {}).get("current", 0)
        hp_max = char.get("hp", {}).get("max", 0)
        xp_cur = char.get("xp", {}).get("current", 0)
        xp_next = char.get("xp", {}).get("next_level", 0)
        level = char.get("level", 1)

        print("=" * 68)
        print(f"  INVENTORY: {name}")
        print("=" * 68)
        print(f"  Gold: {gold}₽  |  HP: {hp_cur}/{hp_max}  |  XP: {xp_cur}/{xp_next}  |  Level: {level}")
        print("=" * 68)

        stackable = self.inventory.get("stackable", {})
        unique = self.inventory.get("unique", [])

        if category:
            category = category.lower()
            if category not in list(ITEM_CATEGORIES.keys()) + ["misc"]:
                print(f"[ERROR] Unknown category '{category}'. "
                      f"Available: {', '.join(list(ITEM_CATEGORIES.keys()) + ['misc'])}",
                      file=sys.stderr)
                return
            print(f"  Filter: {category.upper()}")
            print("-" * 68)
            stackable = {k: v for k, v in stackable.items()
                         if self._categorize_item(k) == category}
            unique = [i for i in unique if self._categorize_item(i) == category]

        if stackable:
            print("\nSTACKABLE ITEMS:")
            max_len = max(len(name) for name in stackable.keys()) if stackable else 0
            for item, qty in sorted(stackable.items()):
                dots = '.' * (max_len + 5 - len(item))
                print(f"  {item} {dots} {qty}")
        else:
            print("\nSTACKABLE ITEMS: (none)")

        if unique:
            print("\nUNIQUE ITEMS:")
            for item in unique:
                print(f"  • {item}")
        else:
            print("\nUNIQUE ITEMS: (none)")

        custom_stats = char.get("custom_stats", {})
        if custom_stats:
            print("\nCUSTOM STATS:")
            max_len = max(len(name) for name in custom_stats.keys())
            for stat_name, stat_data in custom_stats.items():
                current = stat_data.get("current", stat_data.get("value", 0))
                max_val = stat_data.get("max", 100)
                dots = '.' * (max_len + 5 - len(stat_name))
                print(f"  {stat_name.capitalize()} {dots} {current}/{max_val}")

        print("\n" + "=" * 68)


def main():
    """CLI interface"""
    import argparse

    parser = argparse.ArgumentParser(description="Unified Inventory Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    update_parser = subparsers.add_parser('update', help='Update inventory/stats')
    update_parser.add_argument('character', help='Character name')
    update_parser.add_argument('--gold', type=int, help='Add/remove gold (e.g., +100, -50)')
    update_parser.add_argument('--hp', type=int, help='Add/remove HP')
    update_parser.add_argument('--xp', type=int, help='Add/remove XP')
    update_parser.add_argument('--add', nargs=2, action='append', metavar=('ITEM', 'QTY'),
                              help='Add stackable item (name quantity)')
    update_parser.add_argument('--remove', nargs=2, action='append', metavar=('ITEM', 'QTY'),
                              help='Remove stackable item (name quantity)')
    update_parser.add_argument('--set', nargs=2, action='append', metavar=('ITEM', 'QTY'),
                              help='Set exact quantity of item')
    update_parser.add_argument('--add-unique', action='append', metavar='ITEM',
                              help='Add unique item')
    update_parser.add_argument('--remove-unique', action='append', metavar='ITEM',
                              help='Remove unique item')
    update_parser.add_argument('--stat', nargs=2, action='append', metavar=('NAME', 'CHANGE'),
                              help='Modify custom stat (e.g., hunger +10)')
    update_parser.add_argument('--test', action='store_true',
                              help='Test mode: validate but do not apply changes')

    show_parser = subparsers.add_parser('show', help='Show full inventory')
    show_parser.add_argument('character', help='Character name')
    show_parser.add_argument('--category', choices=['weapon', 'ammo', 'food', 'medicine', 'artifact', 'misc'],
                             help='Filter by item category')

    transfer_parser = subparsers.add_parser('transfer', help='Transfer items to NPC/character')
    transfer_parser.add_argument('target', help='Target name (NPC or character)')
    transfer_parser.add_argument('--item', nargs=2, action='append', metavar=('ITEM', 'QTY'),
                                 help='Stackable item to transfer (name quantity)')
    transfer_parser.add_argument('--unique', action='append', metavar='ITEM',
                                 help='Unique item to transfer')
    transfer_parser.add_argument('--test', action='store_true',
                                 help='Test mode: validate but do not apply changes')

    loot_parser = subparsers.add_parser('loot', help='Quick loot (gold + items + xp)')
    loot_parser.add_argument('character', help='Character name')
    loot_parser.add_argument('--gold', type=int, help='Gold amount')
    loot_parser.add_argument('--items', nargs='+', metavar='ITEM:QTY',
                            help='Items in format ItemName:Quantity')
    loot_parser.add_argument('--xp', type=int, help='XP amount')
    loot_parser.add_argument('--test', action='store_true',
                            help='Test mode: validate but do not apply changes')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    active_campaign_file = Path("world-state/active-campaign.txt")
    if not active_campaign_file.exists():
        print("[ERROR] No active campaign found", file=sys.stderr)
        sys.exit(1)

    campaign_name = active_campaign_file.read_text().strip()
    campaign_path = Path(f"world-state/campaigns/{campaign_name}")

    manager = InventoryManager(campaign_path)

    if args.command == 'show':
        manager.show_inventory()

    elif args.command == 'update':
        operations = {}

        if args.gold:
            operations['gold'] = args.gold
        if args.hp:
            operations['hp'] = args.hp
        if args.xp:
            operations['xp'] = args.xp

        if args.add:
            operations['add'] = {item: int(qty) for item, qty in args.add}
        if args.remove:
            operations['remove'] = {item: int(qty) for item, qty in args.remove}
        if args.set:
            operations['set'] = {item: int(qty) for item, qty in args.set}

        if args.add_unique:
            operations['add_unique'] = args.add_unique
        if args.remove_unique:
            operations['remove_unique'] = args.remove_unique

        if args.stat:
            operations['custom_stats'] = {stat: int(val) for stat, val in args.stat}

        success = manager.apply_transaction(operations, test_mode=args.test)
        sys.exit(0 if success else 1)

    elif args.command == 'loot':
        operations = {}

        if args.gold:
            operations['gold'] = args.gold
        if args.xp:
            operations['xp'] = args.xp

        if args.items:
            operations['add'] = {}
            for item_spec in args.items:
                if ':' in item_spec:
                    item, qty = item_spec.rsplit(':', 1)
                    operations['add'][item] = int(qty)
                else:
                    operations['add'][item_spec] = 1

        success = manager.apply_transaction(operations, test_mode=args.test)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
