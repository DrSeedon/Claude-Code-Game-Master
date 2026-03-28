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

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))
from module_data import ModuleDataManager

# Import colors for formatted output
try:
    from lib.colors import Colors
except ImportError:
    try:
        from colors import Colors
    except ImportError:
        class Colors:
            RESET = RS = ""
            RED = R = ""
            GREEN = G = ""
            YELLOW = Y = ""
            CYAN = C = ""
            BOLD = B = ""
            BOLD_RED = BR = ""
            BOLD_GREEN = BG = ""
            BOLD_YELLOW = BY = ""
            BOLD_CYAN = BC = ""
            DIM = DM = ""
            MAGENTA = ""
from currency import load_config, format_money, format_delta, parse_money, migrate_gold, can_afford
from dice import roll as dice_roll, roll_formatted as dice_roll_formatted
from world_graph import WorldGraph


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
        self.module_data_mgr = ModuleDataManager(campaign_path)
        self.npc_name = npc_name
        self.is_npc = npc_name is not None
        self.currency_config = load_config(campaign_path)
        self._wg = WorldGraph(str(campaign_path))
        self.character = self._load_character()
        self.inventory = self._load_inventory()
        self.changes_log = []

    # --- Load / Save ---

    def _load_character(self) -> Dict:
        if self.is_npc:
            return self._load_npc_as_character()

        node = self._wg.get_node("player:active")
        if not node:
            raise FileNotFoundError("Player node not found in world.json")
        char = dict(node.get("data", {}))
        char["name"] = node.get("name", char.get("name", "Player"))
        if char.get('money') is None:
            char['money'] = migrate_gold(char.get('gold', 0), self.currency_config)
        cs_data = self.module_data_mgr.load("custom-stats")
        if cs_data:
            char['custom_stats'] = cs_data.get('character_stats', {})
        return char

    def _load_npc_as_character(self) -> Dict:
        npc_id = self._wg._resolve_id(self.npc_name, "npc")
        if not npc_id:
            raise ValueError(f"NPC '{self.npc_name}' not found")
        node = self._wg.get_node(npc_id)
        if not node:
            raise ValueError(f"NPC '{self.npc_name}' not found")
        npc_data = node.get("data", {})
        if not npc_data.get('is_party_member') and not npc_data.get('party_member'):
            raise ValueError(f"'{self.npc_name}' is not a party member. Use 'dm-npc.sh promote' first.")
        sheet = npc_data.get('character_sheet', {})
        raw_money = sheet.get('money', None)
        if raw_money is None:
            raw_money = migrate_gold(sheet.get('gold', 0), self.currency_config)
        char = {
            'name': node.get('name', self.npc_name),
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
        char_name = save_data.pop("name", "Player")
        self._wg.update_node("player:active", {"name": char_name, "data": save_data})
        save_data["name"] = char_name
        if custom_stats:
            self.character['custom_stats'] = custom_stats
            cs_data = self.module_data_mgr.load("custom-stats") or {}
            cs_data['character_stats'] = custom_stats
            self.module_data_mgr.save("custom-stats", cs_data)

    def _save_npc_character(self):
        npc_id = self._wg._resolve_id(self.npc_name, "npc")
        if not npc_id:
            return
        node = self._wg.get_node(npc_id)
        if not node:
            return
        npc_data = dict(node.get("data", {}))
        sheet = npc_data.setdefault('character_sheet', {})
        sheet['hp'] = self.character.get('hp', {'current': 10, 'max': 10})
        sheet['ac'] = self.character.get('ac', 10)
        sheet['money'] = self.character.get('money', 0)
        sheet.pop('gold', None)
        xp = self.character.get('xp', {})
        sheet['xp'] = xp.get('current', 0) if isinstance(xp, dict) else xp
        sheet['stats'] = self.character.get('stats', {})
        sheet['level'] = self.character.get('level', 1)
        self._wg.update_node(npc_id, {"data": npc_data})

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
        self._dice_rolls = operations.pop('_dice_rolls', {})

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
                old = round(stat[key], 2)
                new = round(old + change, 2)
                min_val = stat.get("min", 0)
                max_val = stat.get("max")
                new = max(min_val, new)
                if max_val is not None:
                    new = min(max_val, new)
                stat[key] = round(new, 2)
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
        G = Colors.G
        R = Colors.R
        C = Colors.C
        DM = Colors.DM
        RS = Colors.RS
        B = Colors.B

        reason_str = f" {DM}— {self.reason}{RS}" if getattr(self, 'reason', None) else ""
        print(f"  {B}INVENTORY UPDATE:{RS} {who}{npc_tag}{reason_str}")

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
                    dice_info = getattr(self, '_dice_rolls', {}).get(stat_name)
                    dice_str = f" 🎲{dice_info[0]}={delta:+d}" if dice_info else ""
                    print(f"  📊 {stat_name}: {old} → {C}{new}{RS} {color}({delta:+d}){RS}{dice_str}")

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
                has_tag = bool(re.search(r'\[\d+(?:\.\d+)?kg\]', item))
                if has_tag:
                    print(f"  {G}+{RS} {item}")
                else:
                    w = self._get_unique_weight(item)
                    print(f"  {G}+{RS} {item} {DM}[{w}kg]{RS}")

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
        npc_id = self._wg._resolve_id(name, "npc")
        if not npc_id:
            return False
        node = self._wg.get_node(npc_id)
        if not node:
            return False
        npc_data = node.get("data", {})
        return npc_data.get('is_party_member', False) or npc_data.get('party_member', False)

    def _is_player_name(self, name: str) -> bool:
        node = self._wg.get_node("player:active")
        if not node:
            return False
        return node.get('name', '').lower() == name.lower()

    # --- Drop (combat) ---

    def remove_item(self, item_name: str, quantity: Optional[int] = None, is_unique: bool = False) -> bool:
        R = Colors.R
        C = Colors.C
        B = Colors.B
        DM = Colors.DM
        RS = Colors.RS
        who = self.character.get('name', 'Character')
        npc_tag = f" {DM}[NPC]{RS}" if self.is_npc else ""

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
            self._save_inventory()
            print("=" * 68)
            print(f"  {B}INVENTORY REMOVE:{RS} {who}{npc_tag}")
            print(f"  {R}\u2212{RS} {found}")
            return True

        current_qty = self._get_stackable_qty(item_name)
        if current_qty == 0:
            print(f"[ERROR] Item '{item_name}' not found in inventory", file=sys.stderr)
            return False

        rm_qty = quantity if quantity else current_qty
        if rm_qty > current_qty:
            rm_qty = current_qty

        w_each = self._get_stackable_weight(item_name)
        new_qty = current_qty - rm_qty
        self._set_stackable(item_name, new_qty, w_each)
        self._save_inventory()

        print("=" * 68)
        print(f"  {B}INVENTORY REMOVE:{RS} {who}{npc_tag}")
        print(f"  {R}\u2212{RS} {item_name} x{rm_qty} {DM}[{w_each}kg ea]{RS}")
        if new_qty > 0:
            print(f"  {DM}Remaining: {new_qty}{RS}")
        return True

    # --- Status (compact, for session start) ---

    def show_status(self):
        B = Colors.B
        C = Colors.C
        G = Colors.G
        Y = Colors.Y
        R = Colors.R
        DM = Colors.DM
        M = Colors.MAGENTA
        RS = Colors.RS

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

        hp_pct = hp_cur / hp_max if hp_max > 0 else 1
        hp_color = G if hp_pct > 0.5 else (Y if hp_pct > 0.25 else R)
        w_status = weight_info['status']
        w_color = G if w_status == "Normal" else (Y if w_status in ("Encumbered", "Heavy") else R)

        print(f"{B}🎒 {name}{RS}")
        print(f"  ❤️  {hp_color}{hp_cur}/{hp_max}{RS}  │  LVL {B}{level}{RS}  │  ⭐ {C}{xp_cur}/{xp_next}{RS}  │  💰 {C}{format_money(money, self.currency_config)}{RS}")
        print(f"  ⚖️  {w_color}{weight_info['total_weight']}/{weight_info['capacity']} kg{RS} ({w_color}{w_status}{RS})")

        stackable = self.inventory.get("stackable", {})
        unique = self.inventory.get("unique", [])
        if stackable:
            print()
            items_display = []
            for item_name, val in stackable.items():
                qty = val.get("qty", 0) if isinstance(val, dict) else val
                w = val.get("weight", 0.5) if isinstance(val, dict) else 0.5
                items_display.append((item_name, qty, w))
            if items_display:
                max_len = max(len(n) for n, *_ in items_display)
                for item_name, qty, w in items_display:
                    dots = '.' * (max_len + 3 - len(item_name))
                    total_w = round(qty * w, 2)
                    print(f"    {item_name} {DM}{dots}{RS} {C}x{qty}{RS}  {DM}({w}kg ea = {total_w}kg){RS}")
        if unique:
            for item in unique:
                print(f"    {M}•{RS} {item}")

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
        B = Colors.B
        C = Colors.C
        G = Colors.G
        Y = Colors.Y
        R = Colors.R
        DM = Colors.DM
        M = Colors.MAGENTA
        RS = Colors.RS

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

        hp_pct = hp_cur / hp_max if hp_max > 0 else 1
        hp_color = G if hp_pct > 0.5 else (Y if hp_pct > 0.25 else R)

        weight_info = self.calculate_weight()
        w_status = weight_info['status']
        w_color = G if w_status == "Normal" else (Y if w_status in ("Encumbered", "Heavy") else R)
        npc_tag = f" {DM}[NPC]{RS}" if self.is_npc else ""

        print(f"  {B}🎒 {name}{RS}{npc_tag}")
        print(f"  {DM}────────────────────────────────────────{RS}")
        print(f"  💰 {C}{format_money(gold, self.currency_config)}{RS}  │  ❤️  {hp_color}{hp_cur}/{hp_max}{RS}  │  ⭐ {C}{xp_cur}/{xp_next}{RS}  │  LVL {B}{level}{RS}")
        print(f"  ⚖️  {w_color}{weight_info['total_weight']}/{weight_info['capacity']} kg{RS} ({w_color}{w_status}{RS})", end="")
        if weight_info['speed_penalty'] > 0 and not weight_info['immobile']:
            print(f"  │  {R}−{weight_info['speed_penalty']} ft{RS}", end="")
        if weight_info['disadvantage']:
            print(f"  │  {R}{B}DISADVANTAGE{RS}", end="")
        if weight_info['immobile']:
            print(f"  │  {R}{B}CANNOT MOVE{RS}", end="")
        print()

        stackable = self.inventory.get("stackable", {})
        unique = self.inventory.get("unique", [])

        if category:
            category = category.lower()
            if category not in list(ITEM_CATEGORIES.keys()) + ["misc"]:
                print(f"[ERROR] Unknown category '{category}'.", file=sys.stderr)
                return
            print(f"  {Y}Filter: {category.upper()}{RS}")
            stackable = {k: v for k, v in stackable.items()
                         if self._categorize_item(k) == category}
            unique = [i for i in unique if self._categorize_item(i) == category]

        if stackable:
            print(f"\n  {B}STACKABLE{RS}")
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
                    print(f"  {item_name} {DM}{dots}{RS} {C}x{qty}{RS}  {DM}({w}kg ea = {total_w}kg){RS}")

        if unique:
            print(f"\n  {B}UNIQUE{RS}")
            for item in unique:
                w = self._get_unique_weight(item)
                has_weight_tag = bool(re.search(r'\[\d+(?:\.\d+)?kg\]', item))
                if has_weight_tag:
                    print(f"  {M}•{RS} {item}")
                else:
                    print(f"  {M}•{RS} {item} {DM}[{w}kg]{RS}")

        if not stackable and not unique:
            print(f"\n  {DM}(пусто){RS}")

        custom_stats = char.get("custom_stats", {})
        if custom_stats:
            print(f"\n  {B}STATS{RS}")
            max_len = max(len(n) for n in custom_stats.keys())
            for stat_name, stat_data in custom_stats.items():
                current = stat_data.get("current", stat_data.get("value", 0))
                max_val = stat_data.get("max", 100)
                pct = current / max_val if max_val > 0 else 0
                bar_len = 10
                filled = int(pct * bar_len)
                bar = f"{C}{'█' * filled}{DM}{'░' * (bar_len - filled)}{RS}"
                dots = '.' * (max_len + 3 - len(stat_name))
                print(f"  {stat_name.capitalize()} {DM}{dots}{RS} {bar} {C}{current}{RS}/{max_val}")

        print()

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
        npc_nodes = self._wg.list_nodes(node_type="npc")

        player_name = self.character.get('name', 'Player')
        player_weight = self.calculate_weight()
        print("=" * 68)
        print("  PARTY INVENTORY SUMMARY")
        print("=" * 68)
        print(f"\n  ► {player_name} (PLAYER)")
        print(f"    Weight: {player_weight['total_weight']}/{player_weight['capacity']} kg — {player_weight['status']}")

        for node in npc_nodes:
            npc_data = node.get("data", {})
            if not npc_data.get('is_party_member') and not npc_data.get('party_member'):
                continue
            npc_name = node.get("name", node["id"])
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
    wg = WorldGraph(str(campaign_path))
    player = wg.get_node("player:active")
    if player and player.get("name", "").lower() == name.lower():
        return None
    npc_id = wg._resolve_id(name, "npc")
    if npc_id:
        node = wg.get_node(npc_id)
        return node.get("name", name) if node else None
    return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Unified Inventory Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    update_parser = subparsers.add_parser('update', help='Update inventory/stats')
    update_parser.add_argument('character', help='Character or NPC name')
    update_parser.add_argument('--gold', type=str, action='append', help='Add/remove money: int (base units) or "2g 5s", "-3gp". Can specify multiple times.')
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
    update_parser.add_argument('--reason', '-r', help='Reason for change (shown in output)')

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
    loot_parser.add_argument('--gold', type=str, action='append', help='Money to add: int (base units) or "2g 5s". Can specify multiple times.')
    loot_parser.add_argument('--items', nargs='+', metavar='ITEM:QTY[:WEIGHT]')
    loot_parser.add_argument('--xp', type=int)
    loot_parser.add_argument('--test', action='store_true')
    loot_parser.add_argument('--reason', '-r', help='Reason for loot (shown in output)')

    subparsers.add_parser('status', help='Compact status for session start')

    remove_parser = subparsers.add_parser('remove', help='Remove item from inventory (sold, destroyed, consumed)')
    remove_parser.add_argument('character', help='Character or NPC name')
    remove_parser.add_argument('item', help='Item to remove')
    remove_parser.add_argument('--qty', type=int)
    remove_parser.add_argument('--unique', action='store_true')

    use_parser = subparsers.add_parser('use', help='Use consumable (auto-lookup wiki for effects)')
    use_parser.add_argument('character', help='Character or NPC name')
    use_parser.add_argument('item', help='Item name to use')
    use_parser.add_argument('--qty', type=int, default=1, help='Quantity to use (default: 1)')

    craft_parser = subparsers.add_parser('craft', help='Craft item from wiki recipe (auto-check ingredients, roll skill)')
    craft_parser.add_argument('character', help='Character or NPC name')
    craft_parser.add_argument('item', help='Wiki item ID or name to craft')
    craft_parser.add_argument('--qty', type=int, default=1, help='How many to craft (default: 1)')
    craft_parser.add_argument('--check', action='store_true', help='Only check if craftable, do not craft')

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
    manager.reason = getattr(args, 'reason', None)

    if args.command == 'show':
        manager.show_inventory(getattr(args, 'category', None))

    elif args.command == 'weigh':
        manager.show_weight_breakdown()

    elif args.command == 'remove':
        if manager.remove_item(args.item, args.qty, args.unique):
            G = Colors.G
            DM = Colors.DM
            RS = Colors.RS
            weight_info = manager.calculate_weight()
            print(f"  {DM}⚖️  {G}{weight_info['total_weight']}/{weight_info['capacity']} kg{RS} {DM}({weight_info['status']}){RS}")
            print("=" * 68)

    elif args.command == 'update':
        operations = {}
        if args.gold:
            total_gold = 0
            for g in args.gold:
                try:
                    val = parse_money(g, manager.currency_config)
                    if str(g).lstrip().startswith('-'):
                        val = -abs(val)
                    total_gold += val
                except ValueError:
                    print(f"[ERROR] Invalid gold amount: {g}", file=sys.stderr)
                    sys.exit(1)
            operations['gold'] = total_gold
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
            _dice_re = re.compile(r'\d*d\d+', re.IGNORECASE)
            custom_stats = {}
            dice_rolls = {}
            for stat, val in args.stat:
                negate = val.startswith('neg') or val.startswith('NEG')
                clean_val = val[3:] if negate else val
                if _dice_re.search(clean_val):
                    roll_result = dice_roll(clean_val)
                    if negate:
                        roll_result = -roll_result
                    custom_stats[stat] = roll_result
                    dice_rolls[stat] = (f"-{clean_val}" if negate else clean_val, roll_result)
                else:
                    custom_stats[stat] = int(val)
            operations['custom_stats'] = custom_stats
            operations['_dice_rolls'] = dice_rolls

        success = manager.apply_transaction(operations, test_mode=args.test)
        sys.exit(0 if success else 1)

    elif args.command == 'loot':
        operations = {}
        if args.gold:
            total_gold = 0
            for g in args.gold:
                try:
                    val = parse_money(g, manager.currency_config)
                    if str(g).lstrip().startswith('-'):
                        val = -abs(val)
                    total_gold += val
                except ValueError:
                    print(f"[ERROR] Invalid gold amount: {g}", file=sys.stderr)
                    sys.exit(1)
            operations['gold'] = total_gold
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

    elif args.command == 'use':
        wg = WorldGraph(campaign_path)
        _use_consumable(manager, wg, args.item, args.qty)
        sys.exit(0)

    elif args.command == 'craft':
        wg = WorldGraph(campaign_path)
        _craft_item(manager, wg, args.item, args.qty, args.check)
        sys.exit(0)


def _wiki_lookup(wg: 'WorldGraph', item_id: str) -> Optional[dict]:
    rid = wg._resolve_id(item_id) or item_id
    node = wg.get_node(rid)
    if not node:
        return None
    result = {
        "_id": rid,
        "name": node.get("name", rid),
        "type": node.get("type", "misc"),
    }
    data = node.get("data", {})
    result.update({k: v for k, v in data.items()})
    return result


def _craft_item(manager, wg: 'WorldGraph', item_id: str, qty: int = 1, check_only: bool = False) -> bool:
    B = Colors.B; RS = Colors.RS; C = Colors.C; G = Colors.G
    R = Colors.R; DM = Colors.DM; Y = Colors.Y

    entity = _wiki_lookup(wg, item_id)
    if not entity:
        print(f"[ERROR] '{item_id}' not found in wiki", file=sys.stderr)
        return False

    recipe = entity.get('recipe')
    if not recipe:
        print(f"[ERROR] '{entity.get('name', item_id)}' has no recipe in wiki", file=sys.stderr)
        return False

    name = entity.get('name', item_id)
    eid = entity.get('_id', item_id)
    dc = recipe.get('dc', 10)
    skill_name = recipe.get('skill', 'алхимия')
    ingredients = recipe.get('ingredients', {})

    char = manager.character
    skills = char.get('skills', {})
    skill_data = skills.get(skill_name, {})
    if isinstance(skill_data, dict):
        skill_bonus = skill_data.get('total', 0)
        dc_mod = skill_data.get('dc_mod', 0)
    else:
        skill_bonus = int(skill_data)
        dc_mod = 0

    effective_dc = dc + dc_mod

    missing = []
    inv = manager.inventory
    stackable = inv.get('stackable', {})
    for ing_id, ing_qty in ingredients.items():
        needed = ing_qty * qty
        ing_entity = _wiki_lookup(wg, ing_id)
        ing_name = ing_entity.get('name', ing_id) if ing_entity else ing_id
        have = 0
        for inv_name, inv_data in stackable.items():
            if inv_name.lower() == ing_name.lower() or ing_name.lower().startswith(inv_name.lower()) or inv_name.lower().startswith(ing_name.lower().split('(')[0].strip()):
                have = inv_data if isinstance(inv_data, int) else inv_data.get('qty', 0)
                break
        if have < needed:
            missing.append(f"{ing_name}: нужно {needed}, есть {have}")

    print(f"{'=' * 60}")
    print(f"  {B}CRAFT: {name}{RS}" + (f" x{qty}" if qty > 1 else ""))
    print(f"  {DM}Skill: {skill_name} +{skill_bonus}, DC: {dc}{'+' + str(dc_mod) if dc_mod else ''} = {effective_dc}{RS}")
    print(f"  Ингредиенты:")
    for ing_id, ing_qty in ingredients.items():
        ing_entity = _wiki_lookup(wg, ing_id)
        ing_name = ing_entity.get('name', ing_id) if ing_entity else ing_id
        needed = ing_qty * qty
        have = 0
        for inv_name, inv_data in stackable.items():
            if inv_name.lower() == ing_name.lower() or ing_name.lower().startswith(inv_name.lower()) or inv_name.lower().startswith(ing_name.lower().split('(')[0].strip()):
                have = inv_data if isinstance(inv_data, int) else inv_data.get('qty', 0)
                break
        status = f"{G}✓{RS}" if have >= needed else f"{R}✗{RS}"
        print(f"    {status} {ing_name}: {needed} (есть {have})")

    auto = (1 + skill_bonus) >= effective_dc
    if auto:
        print(f"  {G}→ АВТОУСПЕХ (1+{skill_bonus} >= {effective_dc}){RS}")
    else:
        min_roll = effective_dc - skill_bonus
        chance = max(0, min(100, (21 - min_roll) * 5))
        print(f"  {Y}→ Бросок нужен (мин. {min_roll} на d20, шанс {chance}%){RS}")

    if missing:
        print(f"\n  {R}НЕ ХВАТАЕТ:{RS}")
        for m in missing:
            print(f"    {R}✗ {m}{RS}")
        print(f"{'=' * 60}")
        return False

    if check_only:
        print(f"\n  {Y}[CHECK ONLY — не крафтим]{RS}")
        print(f"{'=' * 60}")
        return True

    def _resolve_ing_names():
        names = {}
        for ing_id in ingredients:
            ing_entity = _wiki_lookup(wg, ing_id)
            wiki_name = ing_entity.get('name', ing_id) if ing_entity else ing_id
            matched_inv_name = wiki_name
            for inv_name in stackable:
                if inv_name.lower() == wiki_name.lower() or wiki_name.lower().startswith(inv_name.lower()) or inv_name.lower().startswith(wiki_name.lower().split('(')[0].strip()):
                    matched_inv_name = inv_name
                    break
            names[ing_id] = matched_inv_name
        return names

    ing_names = _resolve_ing_names()

    if auto:
        print()
        ops = {'remove': {}, 'add': {}}
        for ing_id, ing_qty in ingredients.items():
            ops['remove'][ing_names[ing_id]] = ing_qty * qty
        ops['add'][name] = qty
        manager.reason = f"скрафтил {name}" + (f" x{qty}" if qty > 1 else "")
        manager.apply_transaction(ops)
        print(f"{'=' * 60}")
        return True

    successes = 0
    crits = 0
    failures = 0
    fumbles = 0
    print()
    for i in range(1, qty + 1):
        label = f"({i}/{qty}) " if qty > 1 else ""
        roll = dice_roll("1d20")
        total_roll = roll + skill_bonus
        if roll == 1:
            print(f"  {label}🎲 [{roll}]+{skill_bonus}={total_roll} vs DC {effective_dc} — {R}💀 FUMBLE{RS}")
            print(f"     {DM}[DM: что-то сломалось/взорвалось/пролилось, двойной расход]{RS}")
            fumbles += 1
        elif total_roll < effective_dc:
            print(f"  {label}🎲 [{roll}]+{skill_bonus}={total_roll} vs DC {effective_dc} — {R}✗ FAIL{RS}")
            print(f"     {DM}[DM: не вышло, ингредиенты потеряны]{RS}")
            failures += 1
        elif roll == 20:
            print(f"  {label}🎲 [{roll}]+{skill_bonus}={total_roll} vs DC {effective_dc} — {G}✓ SUCCESS ⚔ CRIT!{RS}")
            print(f"     {DM}[DM: идеальная варка! Бонусная порция из тех же ингредиентов]{RS}")
            successes += 1
            crits += 1
        else:
            print(f"  {label}🎲 [{roll}]+{skill_bonus}={total_roll} vs DC {effective_dc} — {G}✓ SUCCESS{RS}")
            successes += 1

    ingredient_cost = successes + failures + fumbles * 2
    produced = successes + crits

    ops = {'remove': {}}
    for ing_id, ing_qty in ingredients.items():
        ops['remove'][ing_names[ing_id]] = ing_qty * ingredient_cost
    if produced > 0:
        ops['add'] = {name: produced}

    parts = []
    if successes:
        parts.append(f"{successes} успех")
    if crits:
        parts.append(f"+{crits} бонус (крит)")
    if failures:
        parts.append(f"{failures} провал")
    if fumbles:
        parts.append(f"{fumbles} фамбл (x2 расход)")
    manager.reason = f"крафт {name}: {', '.join(parts)}"
    manager.apply_transaction(ops)
    print(f"{'=' * 60}")
    return successes > 0


def _use_consumable(manager, wg: 'WorldGraph', item_name: str, qty: int = 1) -> bool:
    B = Colors.B; RS = Colors.RS; C = Colors.C; G = Colors.G
    R = Colors.R; DM = Colors.DM; Y = Colors.Y

    entity = _wiki_lookup(wg, item_name)
    if not entity:
        print(f"[ERROR] '{item_name}' not found in wiki", file=sys.stderr)
        return False

    use_data = entity.get('use')
    if not use_data:
        print(f"[ERROR] '{entity.get('name', item_name)}' has no 'use' data in wiki", file=sys.stderr)
        return False

    name = entity.get('name', item_name)
    consume = use_data.get('consume', True)
    effects = use_data.get('effects', [])
    hint = use_data.get('hint', '')

    operations = {}
    if consume:
        operations['remove'] = {name: qty}

    dice_rolls = {}
    custom_stats = {}
    for eff in effects:
        stat = eff.get('stat')
        if not stat:
            continue
        dice_expr = eff.get('dice')
        fixed = eff.get('value')
        if dice_expr:
            _dice_re = re.compile(r'\d*d\d+', re.IGNORECASE)
            negate = dice_expr.startswith('neg')
            clean = dice_expr[3:] if negate else dice_expr
            if _dice_re.search(clean):
                val = dice_roll(clean)
                if negate:
                    val = -val
                custom_stats[stat] = val * qty
                dice_rolls[stat] = (f"-{clean}" if negate else clean, val * qty)
            else:
                custom_stats[stat] = int(dice_expr) * qty
        elif fixed is not None:
            custom_stats[stat] = int(fixed) * qty

    hp_effect = use_data.get('hp')
    if hp_effect:
        if isinstance(hp_effect, str) and re.search(r'\d*d\d+', hp_effect, re.IGNORECASE):
            operations['hp'] = dice_roll(hp_effect) * qty
        else:
            operations['hp'] = int(hp_effect) * qty

    if custom_stats:
        operations['custom_stats'] = custom_stats
        operations['_dice_rolls'] = dice_rolls

    manager.reason = f"использовал {name}" + (f" x{qty}" if qty > 1 else "")
    success = manager.apply_transaction(operations)

    if success and hint:
        print(f"  {DM}[{hint}]{RS}")

    return success


if __name__ == "__main__":
    main()
