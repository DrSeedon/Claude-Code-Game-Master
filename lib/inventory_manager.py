#!/usr/bin/env python3
"""
Unified Inventory Manager
Handles all character/NPC inventory operations in atomic transactions
Player inventory: module-data/inventory-system.json
Party inventory: module-data/inventory-party.json
"""

import json
import sys
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))
# Infrastructure imports
_infra_dir = Path(__file__).parent.parent / ".claude" / "additional" / "infrastructure"
sys.path.insert(0, str(_infra_dir))
from module_data import ModuleDataManager
from currency import load_config, format_money, format_delta, parse_money, migrate_gold, can_afford


ITEM_CATEGORIES = {
    "ammo": ["патрон", "ammo", "mm", "мм", "калибр", "gauge",
             "x39", "x18", "x54", "x19", "x45", "заряд", "charge"],
    "weapon": ["АК-", "АКМ", "АКС", "AK-", "AKM", "ПМ ", "PM ", "SVD", "СВД",
               "Glock", "нож", "knife", "rifle", "pistol", "shotgun", "обрез",
               "дробовик", "винтовк", "автомат", "пистолет", "ружь",
               "DC-15", "DC-17", "Z-6", "E-5", "E-60",
               "меч", "sword", "axe", "топор", "лук ", "bow ",
               "карабин", "штурмовая", "роторная", "вибронож"],
    "food": ["еда", "food", "тушён", "хлеб", "консерв", "колбас", "сухпай",
             "bread", "ration", "вода", "water", "паёк"],
    "medicine": ["бинт", "аптечка", "медик", "антирад", "bandage", "medkit",
                 "medicine", "stim", "промедол", "антибиотик", "медпак",
                 "бакта", "bacta"],
    "artifact": ["артефакт", "artifact", "artefact"],
}

DEFAULT_WEIGHTS = {
    "weapon": 3.0,
    "ammo": 0.02,
    "food": 0.5,
    "medicine": 0.3,
    "artifact": 1.0,
    "misc": 0.5,
}

ENCUMBRANCE_MULTIPLIER = 7

ENCUMBRANCE_TIERS = [
    (1.0, 0, False),
    (1.3, 5, False),
    (1.6, 10, False),
    (2.0, 15, True),
]


class InventoryManager:
    """Unified manager for character/NPC inventory, gold, HP, XP, and custom stats"""

    def __init__(self, campaign_path: Path, npc_name: Optional[str] = None):
        self.campaign_path = campaign_path
        self.character_file = campaign_path / "character.json"
        self.npcs_file = campaign_path / "npcs.json"
        self.module_data_mgr = ModuleDataManager(campaign_path)
        self.npc_name = npc_name
        self.is_npc = npc_name is not None
        self.currency_config = load_config(campaign_path)
        self.character = self._load_character()
        self.inventory = self._load_inventory()
        self.changes_log = []

    # --- Load / Save ---

    def _load_character(self) -> Dict:
        if self.is_npc:
            return self._load_npc_as_character()

        if not self.character_file.exists():
            raise FileNotFoundError(f"Character file not found: {self.character_file}")
        with open(self.character_file, 'r', encoding='utf-8') as f:
            char = json.load(f)
        if char.get('money') is None:
            char['money'] = migrate_gold(char.get('gold', 0), self.currency_config)
        cs_data = self.module_data_mgr.load("custom-stats")
        if cs_data:
            char['custom_stats'] = cs_data.get('character_stats', {})
        return char

    def _load_npc_as_character(self) -> Dict:
        if not self.npcs_file.exists():
            raise FileNotFoundError(f"NPCs file not found: {self.npcs_file}")
        with open(self.npcs_file, 'r', encoding='utf-8') as f:
            npcs = json.load(f)
        if self.npc_name not in npcs:
            raise ValueError(f"NPC '{self.npc_name}' not found")
        npc = npcs[self.npc_name]
        if not npc.get('is_party_member'):
            raise ValueError(f"'{self.npc_name}' is not a party member. Use 'dm-npc.sh promote' first.")
        sheet = npc.get('character_sheet', {})
        raw_money = sheet.get('money', None)
        if raw_money is None:
            raw_money = migrate_gold(sheet.get('gold', 0), self.currency_config)
        char = {
            'name': self.npc_name,
            'level': sheet.get('level', 1),
            'race': sheet.get('race', 'Unknown'),
            'class': sheet.get('class', 'Commoner'),
            'hp': sheet.get('hp', {'current': 10, 'max': 10}),
            'ac': sheet.get('ac', 10),
            'stats': sheet.get('stats', {'str': 10, 'dex': 10, 'con': 10, 'int': 10, 'wis': 10, 'cha': 10}),
            'money': raw_money,
            'xp': sheet.get('xp', 0),
            'conditions': sheet.get('conditions', []),
        }
        if isinstance(char['xp'], int):
            char['xp'] = {'current': char['xp'], 'next_level': 0}
        return char

    def _save_character(self):
        if self.is_npc:
            self._save_npc_character()
            return

        custom_stats = self.character.pop('custom_stats', {})
        save_data = {k: v for k, v in self.character.items() if k not in ("inventory", "gold")}
        with open(self.character_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)
        if custom_stats:
            self.character['custom_stats'] = custom_stats
            cs_data = self.module_data_mgr.load("custom-stats") or {}
            cs_data['character_stats'] = custom_stats
            self.module_data_mgr.save("custom-stats", cs_data)

    def _save_npc_character(self):
        with open(self.npcs_file, 'r', encoding='utf-8') as f:
            npcs = json.load(f)
        sheet = npcs[self.npc_name].setdefault('character_sheet', {})
        sheet['hp'] = self.character.get('hp', {'current': 10, 'max': 10})
        sheet['ac'] = self.character.get('ac', 10)
        sheet['money'] = self.character.get('money', 0)
        sheet.pop('gold', None)
        xp = self.character.get('xp', {})
        sheet['xp'] = xp.get('current', 0) if isinstance(xp, dict) else xp
        sheet['stats'] = self.character.get('stats', {})
        sheet['level'] = self.character.get('level', 1)
        with open(self.npcs_file, 'w', encoding='utf-8') as f:
            json.dump(npcs, f, indent=2, ensure_ascii=False)

    def _load_inventory(self) -> Dict:
        if self.is_npc:
            return self._load_npc_inventory()
        data = self.module_data_mgr.load("inventory-system")
        if not data:
            return {"stackable": {}, "unique": []}
        return data

    def _load_npc_inventory(self) -> Dict:
        party_data = self.module_data_mgr.load("inventory-party")
        if party_data and self.npc_name in party_data:
            return party_data[self.npc_name]
        return {"stackable": {}, "unique": []}

    def _save_inventory(self):
        if self.is_npc:
            party_data = self.module_data_mgr.load("inventory-party") or {}
            party_data[self.npc_name] = self.inventory
            self.module_data_mgr.save("inventory-party", party_data)
            return
        self.module_data_mgr.save("inventory-system", self.inventory)

    # --- Old format migration (player) ---

    def _migrate_old_format(self):
        if "equipment" in self.character:
            print("[MIGRATION] Converting old equipment format...")
            backup_file = self.character_file.with_suffix('.json.backup')
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.character, f, indent=2, ensure_ascii=False)
            stackable = {}
            unique = []
            for item in self.character.get("equipment", []):
                if self._is_unique_item(item):
                    unique.append(item)
                else:
                    item_name, quantity = self._parse_item_quantity(item)
                    stackable[item_name] = stackable.get(item_name, 0) + quantity
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
        match = re.search(r'^(.+?)\s*\((\d+)\s*(?:шт|шт\.|pieces?)?\)$', item)
        if match:
            return match.group(1).strip(), int(match.group(2))
        return item.strip(), 1

    # --- Weight System ---

    def _get_stackable_qty(self, item_name: str) -> int:
        val = self.inventory.get("stackable", {}).get(item_name, 0)
        if isinstance(val, dict):
            return val.get("qty", 0)
        return val

    def _get_stackable_weight(self, item_name: str) -> float:
        val = self.inventory.get("stackable", {}).get(item_name, 0)
        if isinstance(val, dict):
            w = val.get("weight")
            if w is not None:
                return float(w)
        return DEFAULT_WEIGHTS.get(self._categorize_item(item_name), 0.5)

    def _set_stackable(self, item_name: str, qty: int, weight: Optional[float] = None):
        stackable = self.inventory.setdefault("stackable", {})
        if qty <= 0:
            stackable.pop(item_name, None)
            return
        existing = stackable.get(item_name)
        if isinstance(existing, dict):
            existing["qty"] = qty
            if weight is not None:
                existing["weight"] = weight
        else:
            if weight is not None:
                stackable[item_name] = {"qty": qty, "weight": weight}
            else:
                stackable[item_name] = {"qty": qty, "weight": DEFAULT_WEIGHTS.get(self._categorize_item(item_name), 0.5)}

    def _parse_unique_weight(self, item: str) -> Tuple[str, Optional[float]]:
        match = re.search(r'\[(\d+(?:\.\d+)?)kg\]', item)
        if match:
            return item, float(match.group(1))
        return item, None

    def _get_unique_weight(self, item: str) -> float:
        _, w = self._parse_unique_weight(item)
        if w is not None:
            return w
        return DEFAULT_WEIGHTS.get(self._categorize_item(item), 0.5)

    def _add_weight_to_unique(self, item: str, weight: float) -> str:
        if re.search(r'\[\d+(?:\.\d+)?kg\]', item):
            return item
        return f"{item} [{weight}kg]"

    def calculate_weight(self) -> Dict:
        total = 0.0
        breakdown = []

        stackable = self.inventory.get("stackable", {})
        for item_name, val in stackable.items():
            qty = val.get("qty", 0) if isinstance(val, dict) else val
            w = self._get_stackable_weight(item_name)
            item_total = qty * w
            total += item_total
            if item_total > 0:
                breakdown.append({"name": item_name, "qty": qty, "weight_each": w, "weight_total": round(item_total, 2)})

        unique = self.inventory.get("unique", [])
        for item in unique:
            w = self._get_unique_weight(item)
            total += w
            breakdown.append({"name": item, "qty": 1, "weight_each": w, "weight_total": round(w, 2)})

        str_score = self.character.get("stats", {}).get("str", 10)
        capacity = str_score * ENCUMBRANCE_MULTIPLIER
        ratio = total / capacity if capacity > 0 else 999

        speed_penalty = 0
        disadvantage = False
        status = "Normal"
        immobile = False

        if ratio > 2.0:
            speed_penalty = 999
            disadvantage = True
            status = "Immobile"
            immobile = True
        else:
            for threshold, penalty, disadv in ENCUMBRANCE_TIERS:
                if ratio <= threshold:
                    speed_penalty = penalty
                    disadvantage = disadv
                    if penalty == 0:
                        status = "Normal"
                    elif penalty <= 5:
                        status = "Encumbered"
                    elif penalty <= 10:
                        status = "Heavy"
                    else:
                        status = "Overloaded"
                    break

        return {
            "total_weight": round(total, 2),
            "capacity": capacity,
            "ratio": round(ratio, 2),
            "speed_penalty": speed_penalty,
            "disadvantage": disadvantage,
            "status": status,
            "immobile": immobile,
            "breakdown": sorted(breakdown, key=lambda x: x["weight_total"], reverse=True),
        }

    # --- Validation ---

    def validate_transaction(self, operations: Dict) -> Tuple[bool, List[str]]:
        errors = []

        if 'gold' in operations:
            current_money = self.character.get("money", 0)
            delta = operations['gold']
            if not can_afford(current_money, -delta) and delta < 0:
                errors.append(f"Not enough money: need {format_money(abs(delta), self.currency_config)}, have {format_money(current_money, self.currency_config)}")

        if 'hp' in operations:
            hp = self.character.get("hp", {})
            if isinstance(hp, dict):
                current_hp = hp.get("current", 0)
                max_hp = hp.get("max", 0)
            else:
                current_hp = hp
                max_hp = self.character.get("max_hp", hp)
            new_hp = current_hp + operations['hp']
            if new_hp < -max_hp:
                errors.append(f"HP would drop to {new_hp} (too low, character would be dead)")

        for item, quantity in operations.get('remove', {}).items():
            current_qty = self._get_stackable_qty(item)
            if current_qty == 0:
                errors.append(f"Item '{item}' not found in inventory")
            elif current_qty < quantity:
                errors.append(f"Cannot remove {quantity}x {item} (only {current_qty} available)")

        for item in operations.get('remove_unique', []):
            unique = self.inventory.get("unique", [])
            found = any(item.lower() in u.lower() for u in unique)
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

    # --- Transaction ---

    def apply_transaction(self, operations: Dict, test_mode: bool = False):
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
                old = self.character.get("money", 0)
                new = old + operations['gold']
                self.character["money"] = new
                self.changes_log.append(("gold", old, new, operations['gold']))

            if 'hp' in operations:
                hp = self.character.get("hp", {})
                if isinstance(hp, dict):
                    old = hp.get("current", 0)
                    max_hp = hp.get("max", 0)
                else:
                    old = hp
                    max_hp = self.character.get("max_hp", hp)
                new = max(0, old + operations['hp'])
                new = min(new, max_hp)
                if isinstance(self.character.get("hp"), dict):
                    self.character["hp"]["current"] = new
                else:
                    self.character["hp"] = new
                self.changes_log.append(("hp", old, new, operations['hp']))

            if 'xp' in operations:
                xp_data = self.character.get("xp", {})
                if isinstance(xp_data, dict):
                    old = xp_data.get("current", 0)
                else:
                    old = xp_data
                new = old + operations['xp']
                if isinstance(self.character.get("xp"), dict):
                    self.character["xp"]["current"] = new
                else:
                    self.character["xp"] = {"current": new, "next_level": 0}
                self.changes_log.append(("xp", old, new, operations['xp']))

            for item, quantity in operations.get('add', {}).items():
                old = self._get_stackable_qty(item)
                weight = operations.get('_weights', {}).get(item)
                self._set_stackable(item, old + quantity, weight)
                self.changes_log.append(("add", item, old, old + quantity, quantity))

            for item, quantity in operations.get('remove', {}).items():
                old = self._get_stackable_qty(item)
                new = old - quantity
                w = self._get_stackable_weight(item)
                if new <= 0:
                    self._set_stackable(item, 0)
                    self.changes_log.append(("remove", item, old, 0, quantity))
                else:
                    self._set_stackable(item, new, w)
                    self.changes_log.append(("remove", item, old, new, quantity))

            for item, quantity in operations.get('set', {}).items():
                old = self._get_stackable_qty(item)
                weight = operations.get('_weights', {}).get(item)
                self._set_stackable(item, quantity, weight)
                self.changes_log.append(("set", item, old, quantity, quantity - old))

            unique = self.inventory.setdefault("unique", [])
            for item in operations.get('add_unique', []):
                weight = operations.get('_unique_weights', {}).get(item)
                if weight is not None:
                    item = self._add_weight_to_unique(item, weight)
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

            weight_info = self.calculate_weight()
            if weight_info["status"] != "Normal":
                print()
                self._print_weight_warning(weight_info)

            return True

        except Exception as e:
            self.character = original_character
            self.inventory = original_inventory
            self._save_character()
            self._save_inventory()
            print(f"[ERROR] Transaction failed: {e}", file=sys.stderr)
            print("[ROLLBACK] Changes reverted", file=sys.stderr)
            return False

    def _print_weight_warning(self, weight_info: Dict):
        status = weight_info["status"]
        total = weight_info["total_weight"]
        cap = weight_info["capacity"]
        penalty = weight_info["speed_penalty"]
        who = self.character.get('name', 'Character')

        if status == "Immobile":
            print(f"⚠️  {who} IMMOBILE! Weight {total}/{cap} kg (>{cap*2} kg)")
            print(f"   Cannot move. Drop items to continue.")
        elif weight_info["disadvantage"]:
            print(f"⚠️  {who} OVERLOADED! Weight {total}/{cap} kg — speed −{penalty} ft, DISADVANTAGE on attacks")
            print(f"   Drop heavy items in combat: dm-inventory.sh drop \"{who}\" \"[item]\"")
        elif penalty > 0:
            print(f"⚠️  {who} {status.upper()}: Weight {total}/{cap} kg — speed −{penalty} ft")

    def _preview_changes(self, operations: Dict):
        who = self.character.get('name', 'Character')
        print(f"\nWOULD APPLY ({who}):")

        if 'gold' in operations:
            current = self.character.get("money", 0)
            change = operations['gold']
            print(f"  Gold: {format_money(current, self.currency_config)} → {format_money(current + change, self.currency_config)} ({format_delta(change, self.currency_config)})")

        if 'hp' in operations:
            hp = self.character.get("hp", {})
            if isinstance(hp, dict):
                current = hp.get("current", 0)
                max_hp = hp.get("max", 0)
            else:
                current = hp
                max_hp = self.character.get("max_hp", hp)
            change = operations['hp']
            new = max(0, min(max_hp, current + change))
            print(f"  HP: {current}/{max_hp} → {new}/{max_hp} ({change:+d})")

        if 'xp' in operations:
            xp = self.character.get("xp", {})
            current = xp.get("current", 0) if isinstance(xp, dict) else xp
            change = operations['xp']
            print(f"  XP: {current} → {current + change} ({change:+d})")

        for item, qty in operations.get('add', {}).items():
            current = self._get_stackable_qty(item)
            w = operations.get('_weights', {}).get(item, self._get_stackable_weight(item))
            print(f"  + {item} x{qty} (total: {current} → {current + qty}) [{w}kg ea]")

        for item, qty in operations.get('remove', {}).items():
            current = self._get_stackable_qty(item)
            print(f"  - {item} x{qty} (total: {current} → {current - qty})")

        for item in operations.get('add_unique', []):
            print(f"  + {item} [unique]")
        for item in operations.get('remove_unique', []):
            print(f"  - {item} [unique]")

        for stat, change in operations.get('custom_stats', {}).items():
            sd = self.character.get("custom_stats", {}).get(stat, {})
            current = sd.get("current", sd.get("value", 0))
            print(f"  {stat}: {current} → {current + change} ({change:+d})")

    def _print_changes_summary(self):
        who = self.character.get('name', 'Character')
        npc_tag = " [NPC]" if self.is_npc else ""
        print("=" * 68)
        G = "\033[32m"
        R = "\033[31m"
        C = "\033[36m"
        DM = "\033[2m"
        RS = "\033[0m"
        B = "\033[1m"

        print(f"  {B}INVENTORY UPDATE:{RS} {who}{npc_tag}")

        stat_changes = [entry for entry in self.changes_log
                        if entry[0] in ("gold", "hp", "xp", "custom_stat")]
        if stat_changes:
            for entry in stat_changes:
                op = entry[0]
                if op == "gold":
                    old, new, delta = entry[1:4]
                    color = G if delta >= 0 else R
                    print(f"  💰 {format_money(old, self.currency_config)} → {C}{format_money(new, self.currency_config)}{RS} {color}({format_delta(delta, self.currency_config)}){RS}")
                elif op == "hp":
                    old, new, delta = entry[1:4]
                    hp = self.character.get("hp", {})
                    max_hp = hp.get("max", hp) if isinstance(hp, dict) else self.character.get("max_hp", hp)
                    color = G if delta >= 0 else R
                    print(f"  ❤️  {old}/{max_hp} → {C}{new}/{max_hp}{RS} {color}({delta:+d}){RS}")
                elif op == "xp":
                    old, new, delta = entry[1:4]
                    print(f"  ⭐ {old} → {C}{new}{RS} {G}({delta:+d}){RS}")
                elif op == "custom_stat":
                    stat_name, old, new, delta = entry[1:5]
                    color = G if delta >= 0 else R
                    print(f"  📊 {stat_name}: {old} → {C}{new}{RS} {color}({delta:+d}){RS}")

        adds = [data for op, *data in self.changes_log if op == "add"]
        if adds:
            for item, old, new, qty in adds:
                w = self._get_stackable_weight(item)
                print(f"  {G}+{RS} {item} x{qty} {DM}[{w}kg ea]{RS}")

        removes = [data for op, *data in self.changes_log if op == "remove"]
        if removes:
            for item, old, new, qty in removes:
                print(f"  {R}−{RS} {item} x{qty}")

        unique_adds = [data for op, *data in self.changes_log if op == "add_unique"]
        if unique_adds:
            for item, *_ in unique_adds:
                print(f"  {G}+{RS} {item}")

        unique_removes = [data for op, *data in self.changes_log if op == "remove_unique"]
        if unique_removes:
            for item, *_ in unique_removes:
                print(f"  {R}−{RS} {item}")

    def _categorize_item(self, item_name: str) -> str:
        item_lower = item_name.lower()
        for category, keywords in ITEM_CATEGORIES.items():
            for keyword in keywords:
                if keyword.lower() in item_lower:
                    return category
        return "misc"

    # --- Transfer (real, bidirectional) ---

    def transfer_to(self, target_name: str, items: Dict[str, int],
                    unique_items: List[str], test_mode: bool = False) -> bool:
        remove_ops = {}
        if items:
            remove_ops['remove'] = items
        if unique_items:
            remove_ops['remove_unique'] = unique_items
        if not remove_ops:
            print("[ERROR] No items specified for transfer", file=sys.stderr)
            return False

        is_valid, errors = self.validate_transaction(remove_ops)
        if not is_valid:
            print("[ERROR] Transfer validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return False

        is_target_npc = self._is_npc_name(target_name)
        is_target_player = self._is_player_name(target_name)

        if test_mode:
            print("=" * 68)
            print(f"  TEST MODE — TRANSFER: {self.character.get('name', '?')} → {target_name}")
            if is_target_npc:
                print(f"  (Target is party NPC)")
            elif is_target_player:
                print(f"  (Target is player character)")
            else:
                print(f"  (Target not tracked — items removed only)")
            print("=" * 68)
            self._preview_changes(remove_ops)
            print("\n[TEST] No actual changes applied")
            return True

        success = self.apply_transaction(remove_ops)
        if not success:
            return False

        if is_target_npc or is_target_player:
            target_mgr = InventoryManager(
                self.campaign_path,
                npc_name=target_name if is_target_npc else None
            )
            add_ops = {}
            if items:
                add_ops['add'] = {}
                add_ops['_weights'] = {}
                for item_name, qty in items.items():
                    add_ops['add'][item_name] = qty
                    add_ops['_weights'][item_name] = self._get_stackable_weight(item_name)
            if unique_items:
                matched = []
                for search in unique_items:
                    for u in self.changes_log:
                        if u[0] == "remove_unique":
                            matched.append(u[1])
                            break
                add_ops['add_unique'] = matched if matched else unique_items
            target_mgr.apply_transaction(add_ops)

        print(f"\n[TRANSFER] {self.character.get('name', '?')} → {target_name}:")
        for item, qty in items.items():
            print(f"  → {qty}x {item}")
        for item in unique_items:
            print(f"  → {item} [unique]")
        return True

    def _is_npc_name(self, name: str) -> bool:
        if not self.npcs_file.exists():
            return False
        with open(self.npcs_file, 'r', encoding='utf-8') as f:
            npcs = json.load(f)
        return name in npcs and npcs[name].get('is_party_member', False)

    def _is_player_name(self, name: str) -> bool:
        if not self.character_file.exists():
            return False
        with open(self.character_file, 'r', encoding='utf-8') as f:
            char = json.load(f)
        return char.get('name', '') == name

    # --- Drop (combat) ---

    def drop_item(self, item_name: str, quantity: Optional[int] = None, is_unique: bool = False) -> bool:
        if is_unique:
            unique = self.inventory.get("unique", [])
            found = None
            for u in unique:
                if item_name.lower() in u.lower():
                    found = u
                    break
            if not found:
                print(f"[ERROR] Unique item '{item_name}' not found", file=sys.stderr)
                return False
            unique.remove(found)
            w = self._get_unique_weight(found)
            self._save_inventory()
            print(f"[DROPPED] {found} [{w}kg] — on the ground")
            self._log_drop(found, w)
            return True

        current_qty = self._get_stackable_qty(item_name)
        if current_qty == 0:
            print(f"[ERROR] Item '{item_name}' not found in inventory", file=sys.stderr)
            return False

        drop_qty = quantity if quantity else current_qty
        if drop_qty > current_qty:
            drop_qty = current_qty

        w_each = self._get_stackable_weight(item_name)
        new_qty = current_qty - drop_qty
        self._set_stackable(item_name, new_qty, w_each)
        self._save_inventory()

        total_w = round(drop_qty * w_each, 2)
        print(f"[DROPPED] {item_name} x{drop_qty} [{total_w}kg] — on the ground")
        if new_qty > 0:
            print(f"  Remaining: {new_qty}")

        self._log_drop(f"{item_name} x{drop_qty}", total_w)
        return True

    def _log_drop(self, item_desc: str, weight: float):
        location = self.character.get("current_location", "unknown")
        who = self.character.get('name', 'Unknown')
        try:
            subprocess.run(
                ["bash", "tools/dm-note.sh", "dropped_item",
                 f"{who} dropped: {item_desc} [{weight}kg] at {location}"],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=5
            )
        except Exception:
            pass

    # --- Status (compact, for session start) ---

    def show_status(self):
        char = self.character
        name = char.get("name", "Character")
        money = char.get("money", 0)
        hp = char.get("hp", {})
        hp_cur = hp.get("current", 0) if isinstance(hp, dict) else hp
        hp_max = hp.get("max", 0) if isinstance(hp, dict) else hp
        xp = char.get("xp", {})
        xp_cur = xp.get("current", 0) if isinstance(xp, dict) else xp
        xp_next = xp.get("next_level", 300) if isinstance(xp, dict) else 300
        level = char.get("level", 0)
        weight_info = self.calculate_weight()

        print(f"🎒 INVENTORY — {name}")
        print(f"  HP: {hp_cur}/{hp_max} | LVL: {level} | XP: {xp_cur}/{xp_next} | Gold: {format_money(money, self.currency_config)}")
        print(f"  Weight: {weight_info['total_weight']}/{weight_info['capacity']} kg ({weight_info['status']})")

        stackable = self.inventory.get("stackable", {})
        unique = self.inventory.get("unique", [])
        if stackable:
            print()
            for item_name, val in stackable.items():
                qty = val.get("qty", 0) if isinstance(val, dict) else val
                w = val.get("weight", 0.5) if isinstance(val, dict) else 0.5
                print(f"    {item_name:.<30s} x{qty}  ({w}kg ea = {qty*w:.1f}kg)")
        if unique:
            for item in unique:
                print(f"    • {item}")

        party_data = self.module_data_mgr.load("inventory-party")
        if party_data:
            print()
            print("  Party Inventories:")
            for pname, pdata in party_data.items():
                p_stack = pdata.get("stackable", {})
                p_uniq = pdata.get("unique", [])
                p_w = sum(
                    (v.get("qty", 0) * v.get("weight", 0.5) if isinstance(v, dict) else int(v) * 0.5)
                    for v in p_stack.values()
                )
                print(f"    {pname}: {len(p_stack)} stackable, {len(p_uniq)} unique ({p_w:.1f}kg)")

    # --- Show ---

    def show_inventory(self, category: Optional[str] = None):
        char = self.character
        name = char.get("name", "Character")
        gold = char.get("money", 0)
        hp_data = char.get("hp", {})
        if isinstance(hp_data, dict):
            hp_cur = hp_data.get("current", 0)
            hp_max = hp_data.get("max", 0)
        else:
            hp_cur = hp_data
            hp_max = char.get("max_hp", hp_data)
        xp_data = char.get("xp", {})
        if isinstance(xp_data, dict):
            xp_cur = xp_data.get("current", 0)
            xp_next = xp_data.get("next_level", 0)
        else:
            xp_cur = xp_data
            xp_next = 0
        level = char.get("level", 1)

        weight_info = self.calculate_weight()
        npc_tag = " [NPC]" if self.is_npc else ""

        print("=" * 68)
        print(f"  INVENTORY: {name}{npc_tag}")
        print("=" * 68)
        print(f"  Gold: {format_money(gold, self.currency_config)}  |  HP: {hp_cur}/{hp_max}  |  XP: {xp_cur}/{xp_next}  |  Level: {level}")
        print(f"  Weight: {weight_info['total_weight']}/{weight_info['capacity']} kg  |  Status: {weight_info['status']}", end="")
        if weight_info['speed_penalty'] > 0 and not weight_info['immobile']:
            print(f"  |  Speed: −{weight_info['speed_penalty']} ft", end="")
        if weight_info['disadvantage']:
            print(f"  |  DISADVANTAGE", end="")
        if weight_info['immobile']:
            print(f"  |  CANNOT MOVE", end="")
        print()
        print("=" * 68)

        stackable = self.inventory.get("stackable", {})
        unique = self.inventory.get("unique", [])

        if category:
            category = category.lower()
            if category not in list(ITEM_CATEGORIES.keys()) + ["misc"]:
                print(f"[ERROR] Unknown category '{category}'.", file=sys.stderr)
                return
            print(f"  Filter: {category.upper()}")
            print("-" * 68)
            stackable = {k: v for k, v in stackable.items()
                         if self._categorize_item(k) == category}
            unique = [i for i in unique if self._categorize_item(i) == category]

        if stackable:
            print("\nSTACKABLE ITEMS:")
            items_display = []
            for item_name, val in sorted(stackable.items()):
                qty = val.get("qty", 0) if isinstance(val, dict) else val
                w = self._get_stackable_weight(item_name)
                total_w = round(qty * w, 2)
                items_display.append((item_name, qty, w, total_w))
            if items_display:
                max_len = max(len(n) for n, *_ in items_display)
                for item_name, qty, w, total_w in items_display:
                    dots = '.' * (max_len + 3 - len(item_name))
                    print(f"  {item_name} {dots} x{qty}  ({w}kg ea = {total_w}kg)")
        else:
            print("\nSTACKABLE ITEMS: (none)")

        if unique:
            print("\nUNIQUE ITEMS:")
            for item in unique:
                w = self._get_unique_weight(item)
                has_weight_tag = bool(re.search(r'\[\d+(?:\.\d+)?kg\]', item))
                if has_weight_tag:
                    print(f"  • {item}")
                else:
                    print(f"  • {item} [{w}kg]")
        else:
            print("\nUNIQUE ITEMS: (none)")

        custom_stats = char.get("custom_stats", {})
        if custom_stats:
            print("\nCUSTOM STATS:")
            max_len = max(len(n) for n in custom_stats.keys())
            for stat_name, stat_data in custom_stats.items():
                current = stat_data.get("current", stat_data.get("value", 0))
                max_val = stat_data.get("max", 100)
                dots = '.' * (max_len + 5 - len(stat_name))
                print(f"  {stat_name.capitalize()} {dots} {current}/{max_val}")

        print("\n" + "=" * 68)

    def show_weight_breakdown(self):
        weight_info = self.calculate_weight()
        name = self.character.get("name", "Character")
        npc_tag = " [NPC]" if self.is_npc else ""

        print("=" * 68)
        print(f"  WEIGHT BREAKDOWN: {name}{npc_tag}")
        print("=" * 68)
        print(f"  Total: {weight_info['total_weight']} kg / {weight_info['capacity']} kg ({weight_info['ratio']*100:.0f}%)")
        print(f"  Status: {weight_info['status']}", end="")
        if weight_info['speed_penalty'] > 0 and not weight_info['immobile']:
            print(f" | Speed: −{weight_info['speed_penalty']} ft", end="")
        if weight_info['disadvantage']:
            print(f" | DISADVANTAGE", end="")
        if weight_info['immobile']:
            print(f" | CANNOT MOVE", end="")
        print()
        print("-" * 68)

        str_score = self.character.get("stats", {}).get("str", 10)
        cap = weight_info['capacity']
        print(f"\n  STR {str_score} × {ENCUMBRANCE_MULTIPLIER} = {cap} kg capacity")
        print(f"  Normal:     0 – {cap} kg")
        print(f"  Encumbered: {cap} – {round(cap*1.3)} kg (−5 ft)")
        print(f"  Heavy:      {round(cap*1.3)} – {round(cap*1.6)} kg (−10 ft)")
        print(f"  Overloaded: {round(cap*1.6)} – {cap*2} kg (−15 ft + disadvantage)")
        print(f"  Immobile:   > {cap*2} kg")

        print(f"\n  {'ITEM':<35} {'QTY':>5} {'EACH':>8} {'TOTAL':>8}")
        print(f"  {'─'*35} {'─'*5} {'─'*8} {'─'*8}")

        for entry in weight_info['breakdown']:
            n = entry['name'][:35]
            q = entry['qty']
            we = entry['weight_each']
            wt = entry['weight_total']
            print(f"  {n:<35} {q:>5} {we:>7.2f} {wt:>7.2f}")

        print(f"  {'─'*35} {'─'*5} {'─'*8} {'─'*8}")
        print(f"  {'TOTAL':<35} {'':>5} {'':>8} {weight_info['total_weight']:>7.2f}")
        print("\n" + "=" * 68)

    def show_party_inventory(self):
        if not self.npcs_file.exists():
            print("No NPCs file found.")
            return
        with open(self.npcs_file, 'r', encoding='utf-8') as f:
            npcs = json.load(f)

        player_name = self.character.get('name', 'Player')
        player_weight = self.calculate_weight()
        print("=" * 68)
        print("  PARTY INVENTORY SUMMARY")
        print("=" * 68)
        print(f"\n  ► {player_name} (PLAYER)")
        print(f"    Weight: {player_weight['total_weight']}/{player_weight['capacity']} kg — {player_weight['status']}")

        for npc_name, npc_data in npcs.items():
            if not npc_data.get('is_party_member'):
                continue
            try:
                npc_mgr = InventoryManager(self.campaign_path, npc_name=npc_name)
                npc_weight = npc_mgr.calculate_weight()
                str_score = npc_data.get('character_sheet', {}).get('stats', {}).get('str', 10)
                print(f"\n  ► {npc_name} [NPC] (STR {str_score})")
                print(f"    Weight: {npc_weight['total_weight']}/{npc_weight['capacity']} kg — {npc_weight['status']}")
                stackable_count = sum(
                    v.get('qty', 0) if isinstance(v, dict) else v
                    for v in npc_mgr.inventory.get('stackable', {}).values()
                )
                unique_count = len(npc_mgr.inventory.get('unique', []))
                print(f"    Items: {stackable_count} stackable, {unique_count} unique")
            except Exception as e:
                print(f"\n  ► {npc_name} [NPC] — inventory error: {e}")

        print("\n" + "=" * 68)


# --- CLI ---

def _resolve_target(campaign_path: Path, name: str) -> Optional[str]:
    char_file = campaign_path / "character.json"
    if char_file.exists():
        with open(char_file, 'r', encoding='utf-8') as f:
            char = json.load(f)
        if char.get('name', '').lower() == name.lower():
            return None

    npcs_file = campaign_path / "npcs.json"
    if npcs_file.exists():
        with open(npcs_file, 'r', encoding='utf-8') as f:
            npcs = json.load(f)
        for npc_name in npcs:
            if npc_name.lower() == name.lower():
                return npc_name

    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Unified Inventory Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    update_parser = subparsers.add_parser('update', help='Update inventory/stats')
    update_parser.add_argument('character', help='Character or NPC name')
    update_parser.add_argument('--gold', type=str, help='Add/remove money: int (base units) or "2g 5s", "-3gp"')
    update_parser.add_argument('--hp', type=int, help='Add/remove HP')
    update_parser.add_argument('--xp', type=int, help='Add/remove XP')
    update_parser.add_argument('--add', nargs='+', action='append', metavar='ITEM',
                              help='Add stackable: --add "Item" QTY [WEIGHT_KG]')
    update_parser.add_argument('--remove', nargs=2, action='append', metavar=('ITEM', 'QTY'),
                              help='Remove stackable item')
    update_parser.add_argument('--set', nargs='+', action='append', metavar='ITEM',
                              help='Set quantity: --set "Item" QTY [WEIGHT_KG]')
    update_parser.add_argument('--add-unique', action='append', metavar='ITEM',
                              help='Add unique item')
    update_parser.add_argument('--unique-weight', nargs=2, action='append', metavar=('ITEM', 'KG'),
                              help='Set weight for unique item')
    update_parser.add_argument('--remove-unique', action='append', metavar='ITEM',
                              help='Remove unique item')
    update_parser.add_argument('--stat', nargs=2, action='append', metavar=('NAME', 'CHANGE'),
                              help='Modify custom stat')
    update_parser.add_argument('--test', action='store_true', help='Test mode')

    show_parser = subparsers.add_parser('show', help='Show inventory')
    show_parser.add_argument('character', help='Character or NPC name')
    show_parser.add_argument('--category', choices=['weapon', 'ammo', 'food', 'medicine', 'artifact', 'misc'])

    weigh_parser = subparsers.add_parser('weigh', help='Weight breakdown')
    weigh_parser.add_argument('character', help='Character or NPC name')

    party_parser = subparsers.add_parser('party', help='Show all party inventories')

    transfer_parser = subparsers.add_parser('transfer', help='Transfer items')
    transfer_parser.add_argument('target', help='Target name (NPC or player)')
    transfer_parser.add_argument('--from', dest='source', help='Source name (default: player)')
    transfer_parser.add_argument('--item', nargs=2, action='append', metavar=('ITEM', 'QTY'))
    transfer_parser.add_argument('--unique', action='append', metavar='ITEM')
    transfer_parser.add_argument('--test', action='store_true')

    loot_parser = subparsers.add_parser('loot', help='Quick loot')
    loot_parser.add_argument('character', help='Character or NPC name')
    loot_parser.add_argument('--gold', type=str, help='Money to add: int (base units) or "2g 5s"')
    loot_parser.add_argument('--items', nargs='+', metavar='ITEM:QTY[:WEIGHT]')
    loot_parser.add_argument('--xp', type=int)
    loot_parser.add_argument('--test', action='store_true')

    subparsers.add_parser('status', help='Compact status for session start')

    drop_parser = subparsers.add_parser('drop', help='Drop item (combat)')
    drop_parser.add_argument('character', help='Character or NPC name')
    drop_parser.add_argument('item', help='Item to drop')
    drop_parser.add_argument('--qty', type=int)
    drop_parser.add_argument('--unique', action='store_true')

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

    if args.command == 'status':
        manager = InventoryManager(campaign_path)
        manager.show_status()
        sys.exit(0)

    if args.command == 'party':
        manager = InventoryManager(campaign_path)
        manager.show_party_inventory()
        sys.exit(0)

    char_name = getattr(args, 'character', None) or getattr(args, 'source', None)
    npc_name = _resolve_target(campaign_path, char_name) if char_name else None
    manager = InventoryManager(campaign_path, npc_name=npc_name)

    if args.command == 'show':
        manager.show_inventory(getattr(args, 'category', None))

    elif args.command == 'weigh':
        manager.show_weight_breakdown()

    elif args.command == 'drop':
        success = manager.drop_item(args.item, args.qty, args.unique)
        weight_info = manager.calculate_weight()
        if weight_info['status'] == 'Normal':
            print(f"  Weight now: {weight_info['total_weight']}/{weight_info['capacity']} kg — Normal")
        sys.exit(0 if success else 1)

    elif args.command == 'update':
        operations = {}
        if args.gold:
            try:
                operations['gold'] = parse_money(args.gold, manager.currency_config)
                if str(args.gold).lstrip().startswith('-'):
                    operations['gold'] = -abs(operations['gold'])
            except ValueError:
                print(f"[ERROR] Invalid gold amount: {args.gold}", file=sys.stderr)
                sys.exit(1)
        if args.hp:
            operations['hp'] = args.hp
        if args.xp:
            operations['xp'] = args.xp

        if args.add:
            operations['add'] = {}
            operations['_weights'] = {}
            for parts in args.add:
                item_name = parts[0]
                qty = int(parts[1]) if len(parts) > 1 else 1
                operations['add'][item_name] = qty
                if len(parts) > 2:
                    operations['_weights'][item_name] = float(parts[2])

        if args.remove:
            operations['remove'] = {item: int(qty) for item, qty in args.remove}

        if args.set:
            operations['set'] = {}
            operations.setdefault('_weights', {})
            for parts in args.set:
                item_name = parts[0]
                qty = int(parts[1]) if len(parts) > 1 else 1
                operations['set'][item_name] = qty
                if len(parts) > 2:
                    operations['_weights'][item_name] = float(parts[2])

        if args.add_unique:
            operations['add_unique'] = args.add_unique
        if getattr(args, 'unique_weight', None):
            operations['_unique_weights'] = {item: float(kg) for item, kg in args.unique_weight}
        if args.remove_unique:
            operations['remove_unique'] = args.remove_unique

        if args.stat:
            operations['custom_stats'] = {stat: int(val) for stat, val in args.stat}

        success = manager.apply_transaction(operations, test_mode=args.test)
        sys.exit(0 if success else 1)

    elif args.command == 'loot':
        operations = {}
        if args.gold:
            try:
                operations['gold'] = parse_money(args.gold, manager.currency_config)
                if str(args.gold).lstrip().startswith('-'):
                    operations['gold'] = -abs(operations['gold'])
            except ValueError:
                print(f"[ERROR] Invalid gold amount: {args.gold}", file=sys.stderr)
                sys.exit(1)
        if args.xp:
            operations['xp'] = args.xp
        if args.items:
            operations['add'] = {}
            operations['_weights'] = {}
            for item_spec in args.items:
                parts = item_spec.rsplit(':', 2)
                if len(parts) == 3:
                    item, qty, weight = parts[0], int(parts[1]), float(parts[2])
                    operations['add'][item] = qty
                    operations['_weights'][item] = weight
                elif len(parts) == 2:
                    operations['add'][parts[0]] = int(parts[1])
                else:
                    operations['add'][item_spec] = 1
        success = manager.apply_transaction(operations, test_mode=args.test)
        sys.exit(0 if success else 1)

    elif args.command == 'transfer':
        source_name = args.source
        if source_name:
            source_npc = _resolve_target(campaign_path, source_name)
            source_mgr = InventoryManager(campaign_path, npc_name=source_npc)
        else:
            source_mgr = InventoryManager(campaign_path)

        items = {item: int(qty) for item, qty in args.item} if args.item else {}
        unique_items = args.unique or []
        success = source_mgr.transfer_to(args.target, items, unique_items, args.test)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
