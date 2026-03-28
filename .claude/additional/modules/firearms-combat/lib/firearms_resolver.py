#!/usr/bin/env python3
"""
Firearms Combat Resolver — standalone module for modern/STALKER firearms mechanics.

Imports CORE's PlayerManager. CORE has zero knowledge of this module.
DM (Claude) calls this via dm-combat.sh for firearms combat resolution.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.json_ops import JsonOperations
from lib.player_manager import PlayerManager
from lib.campaign_manager import CampaignManager
from lib.world_graph import WorldGraph

from lib.module_data import ModuleDataManager

MODULE_ID = "firearms-combat"


class FirearmsCombatResolver:
    """Resolves firearms combat with automatic attack/damage calculation"""

    def __init__(self, world_state_dir: str = "world-state"):
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign.")

        self.json_ops = JsonOperations(str(self.campaign_dir))
        self.player_mgr = PlayerManager(str(self.campaign_dir.parent.parent))
        self.module_data_mgr = ModuleDataManager(self.campaign_dir)
        self.world_graph = WorldGraph(self.campaign_dir)
        self.firearms_config = self._load_firearms_config()
        self.character = self._load_character()

    def _load_firearms_config(self) -> Dict:
        """Load firearms config from module-data/firearms-combat.json."""
        data = self.module_data_mgr.load(MODULE_ID)
        if not data:
            raise RuntimeError(
                "No firearms config found. "
                "Expected: module-data/firearms-combat.json in campaign directory."
            )
        return data

    def _load_character(self) -> Dict:
        """Load active character — prefers character.json, falls back to current_character in overview"""
        char = self.player_mgr._load_character(None)
        if char:
            return char
        overview = self.json_ops.load_json("campaign-overview.json")
        char_name = overview.get("current_character")
        if not char_name:
            raise RuntimeError("No active character")
        char = self.player_mgr._load_character(char_name)
        if not char:
            raise RuntimeError(f"Character '{char_name}' not found")
        return char

    def _to_kebab(self, name: str) -> str:
        name = re.sub(r"[^a-z0-9]+", "-", name.lower())
        return name.strip("-")

    def _get_weapon_from_world(self, weapon_name: str) -> Optional[Dict]:
        kebab = self._to_kebab(weapon_name)
        node = self.world_graph.get_node(f"weapon:{kebab}")
        if node:
            return node.get("data", {})
        results = self.world_graph.search_nodes(weapon_name, node_type="weapon")
        if results:
            return results[0].get("data", {})
        return None

    def _get_weapon_stats(self, weapon_name: str) -> Dict:
        world_weapon = self._get_weapon_from_world(weapon_name)
        if world_weapon:
            return world_weapon
        raise ValueError(f"Weapon '{weapon_name}' not found in world.json")

    def _get_fire_mode_config(self, mode: str) -> Dict:
        fire_modes = self.firearms_config.get("fire_modes", {})
        mode_config = fire_modes.get(mode)
        if not mode_config:
            raise ValueError(f"Fire mode '{mode}' not found in firearms config")
        return mode_config

    def _get_attack_bonus(self) -> int:
        """Calculate base attack bonus for character"""
        abilities = self.character.get("abilities", {})
        dex_mod = (abilities.get("dex", 10) - 10) // 2
        prof_bonus = self.character.get("proficiency_bonus", 2)

        subclass_bonus = 0
        if self.character.get("subclass") == "Стрелок":
            subclass_bonus = 2

        return dex_mod + prof_bonus + subclass_bonus

    def _is_sharpshooter(self) -> bool:
        """Check if character has Стрелок subclass"""
        return self.character.get("subclass") == "Стрелок"

    def _roll_d20(self) -> int:
        """Roll a d20"""
        return random.randint(1, 20)

    def _roll_damage(self, damage_dice: str) -> int:
        """Roll damage dice (e.g., '2d8+3')"""
        if '+' in damage_dice:
            dice_part, bonus = damage_dice.split('+')
            bonus = int(bonus)
        elif '-' in damage_dice:
            dice_part, bonus_str = damage_dice.split('-')
            bonus = -int(bonus_str)
        else:
            dice_part = damage_dice
            bonus = 0

        num_dice, die_size = dice_part.split('d')
        num_dice = int(num_dice)
        die_size = int(die_size)

        total = sum(random.randint(1, die_size) for _ in range(num_dice))
        return total + bonus

    def _calculate_rounds_per_dnd_round(self, rpm: int) -> int:
        """Calculate how many rounds can be fired in 6 seconds (1 D&D round)"""
        rounds_per_second = rpm / 60
        return int(rounds_per_second * 6)

    def _apply_pen_vs_prot(self, damage: int, pen: int, prot: int) -> int:
        """Apply penetration vs protection damage scaling"""
        if pen > prot:
            return damage
        elif pen <= prot / 2:
            return damage // 4
        else:
            return damage // 2

    def resolve_single(
        self,
        weapon_name: str,
        ammo_available: int,
        targets: List[Dict]
    ) -> Dict:
        weapon = self._get_weapon_stats(weapon_name)
        if ammo_available < 1:
            return self._empty_result(weapon_name, 0, ammo_available, targets)

        base_attack = self._get_attack_bonus()
        target = targets[0]

        roll = self._roll_d20()
        total = roll + base_attack

        hit = False
        crit = False
        if roll == 20:
            hit, crit = True, True
        elif roll == 1:
            hit = False
        elif total >= target["ac"]:
            hit = True

        target_result = {
            "name": target["name"],
            "ac": target["ac"],
            "initial_hp": target["hp"],
            "prot": target["prot"],
            "shots": 1,
            "hits": [{
                "shot_num": 1, "roll": roll, "modifier": base_attack,
                "total": total, "hit": hit, "crit": crit
            }],
            "damage_dealt": 0,
            "final_hp": target["hp"],
            "killed": False
        }

        total_damage = 0
        total_xp = 0

        if hit:
            if crit:
                damage_dice = self._double_dice(weapon["damage"])
            else:
                damage_dice = weapon["damage"]
            raw_damage = self._roll_damage(damage_dice)
            pen, prot = weapon["pen"], target["prot"]
            final_damage = self._apply_pen_vs_prot(raw_damage, pen, prot)
            scaling, scaling_pct = self._get_scaling_label(pen, prot)

            target["hp"] -= final_damage
            target_result["damage_dealt"] = final_damage
            target_result["final_hp"] = target["hp"]
            total_damage = final_damage

            target_result["hits"][0].update({
                "damage_dice": damage_dice, "raw_damage": raw_damage,
                "pen": pen, "prot": prot, "scaling": scaling,
                "scaling_pct": scaling_pct, "final_damage": final_damage
            })

        if target["hp"] <= 0:
            target_result["killed"] = True
            total_xp = 25

        return {
            "weapon": weapon_name,
            "fire_mode": "single",
            "shots_fired": 1,
            "ammo_remaining": ammo_available - 1,
            "ammo_type": weapon.get("ammo_type"),
            "base_attack": base_attack,
            "is_sharpshooter": self._is_sharpshooter(),
            "targets": [target_result],
            "total_damage": total_damage,
            "enemies_killed": 1 if target_result["killed"] else 0,
            "total_xp": total_xp
        }

    def resolve_burst(
        self,
        weapon_name: str,
        ammo_available: int,
        targets: List[Dict]
    ) -> Dict:
        weapon = self._get_weapon_stats(weapon_name)
        fire_mode = self._get_fire_mode_config("burst")

        shots_count = min(ammo_available, fire_mode.get("attacks", 3))
        if shots_count == 0:
            return self._empty_result(weapon_name, 0, ammo_available, targets)

        base_attack = self._get_attack_bonus()
        is_sharpshooter = self._is_sharpshooter()

        if is_sharpshooter:
            penalty_per_shot = fire_mode.get("penalty_per_shot_sharpshooter", -1)
        else:
            penalty_per_shot = fire_mode.get("penalty_per_shot", -2)

        target = targets[0]
        target_result = {
            "name": target["name"],
            "ac": target["ac"],
            "initial_hp": target["hp"],
            "prot": target["prot"],
            "shots": shots_count,
            "hits": [],
            "damage_dealt": 0,
            "final_hp": target["hp"],
            "killed": False
        }

        total_damage = 0
        total_xp = 0

        for shot_num in range(shots_count):
            penalty = shot_num * penalty_per_shot
            attack_mod = base_attack + penalty
            roll = self._roll_d20()
            total = roll + attack_mod

            hit, crit = False, False
            if roll == 20:
                hit, crit = True, True
            elif roll == 1:
                hit = False
            elif total >= target["ac"]:
                hit = True

            shot_data = {
                "shot_num": shot_num + 1, "roll": roll, "modifier": attack_mod,
                "total": total, "hit": hit, "crit": crit
            }

            if hit:
                if crit:
                    damage_dice = self._double_dice(weapon["damage"])
                else:
                    damage_dice = weapon["damage"]
                raw_damage = self._roll_damage(damage_dice)
                pen, prot = weapon["pen"], target["prot"]
                final_damage = self._apply_pen_vs_prot(raw_damage, pen, prot)
                scaling, scaling_pct = self._get_scaling_label(pen, prot)

                target["hp"] -= final_damage
                target_result["damage_dealt"] += final_damage
                total_damage += final_damage

                shot_data.update({
                    "damage_dice": damage_dice, "raw_damage": raw_damage,
                    "pen": pen, "prot": prot, "scaling": scaling,
                    "scaling_pct": scaling_pct, "final_damage": final_damage
                })

            target_result["hits"].append(shot_data)

        target_result["final_hp"] = target["hp"]
        if target["hp"] <= 0:
            target_result["killed"] = True
            total_xp = 25

        return {
            "weapon": weapon_name,
            "fire_mode": "burst",
            "shots_fired": shots_count,
            "ammo_remaining": ammo_available - shots_count,
            "ammo_type": weapon.get("ammo_type"),
            "base_attack": base_attack,
            "is_sharpshooter": is_sharpshooter,
            "targets": [target_result],
            "total_damage": total_damage,
            "enemies_killed": 1 if target_result["killed"] else 0,
            "total_xp": total_xp
        }

    def _double_dice(self, damage_dice: str) -> str:
        if 'd' not in damage_dice:
            return damage_dice
        parts = damage_dice.split('d')
        num_dice = int(parts[0])
        return f"{num_dice * 2}d{parts[1]}"

    def _get_scaling_label(self, pen: int, prot: int) -> Tuple[str, int]:
        if pen > prot:
            return "FULL", 100
        elif pen <= prot / 2:
            return "QUARTER", 25
        else:
            return "HALF", 50

    def _empty_result(self, weapon_name: str, shots: int, ammo: int, targets: List[Dict]) -> Dict:
        return {
            "weapon": weapon_name,
            "fire_mode": "empty",
            "shots_fired": 0,
            "ammo_remaining": ammo,
            "ammo_type": None,
            "base_attack": 0,
            "is_sharpshooter": False,
            "targets": [],
            "total_damage": 0,
            "enemies_killed": 0,
            "total_xp": 0
        }

    def resolve_full_auto(
        self,
        weapon_name: str,
        ammo_available: int,
        targets: List[Dict]
    ) -> Dict:
        """
        Resolve full-auto fire combat

        Args:
            weapon_name: Name of weapon
            ammo_available: Available ammunition
            targets: List of dicts with 'name', 'ac', 'hp', 'prot'

        Returns:
            Dict with combat results
        """
        weapon = self._get_weapon_stats(weapon_name)
        fire_mode = self._get_fire_mode_config("full_auto")

        max_rounds_per_round = self._calculate_rounds_per_dnd_round(weapon["rpm"])
        shots_fired = min(ammo_available, max_rounds_per_round)
        shots_per_target = shots_fired // len(targets)
        if shots_per_target == 0:
            shots_per_target = 1

        max_shots_cap = fire_mode.get("max_shots_per_target", 0)
        if max_shots_cap > 0:
            shots_per_target = min(shots_per_target, max_shots_cap)

        base_attack = self._get_attack_bonus()
        is_sharpshooter = self._is_sharpshooter()

        if is_sharpshooter:
            penalty_per_shot = fire_mode.get("penalty_per_shot_sharpshooter", -2)
        else:
            penalty_per_shot = fire_mode.get("penalty_per_shot", -3)

        results = []
        total_damage = 0
        enemies_killed = 0
        total_xp = 0

        for target_idx, target in enumerate(targets):
            target_result = {
                "name": target["name"],
                "ac": target["ac"],
                "initial_hp": target["hp"],
                "prot": target["prot"],
                "shots": shots_per_target,
                "hits": [],
                "damage_dealt": 0,
                "final_hp": target["hp"],
                "killed": False
            }

            for shot_num in range(shots_per_target):
                penalty = shot_num * penalty_per_shot
                attack_mod = base_attack + penalty

                roll = self._roll_d20()
                total = roll + attack_mod

                hit = False
                crit = False

                if roll == 20:
                    hit = True
                    crit = True
                elif roll == 1:
                    hit = False
                elif total >= target["ac"]:
                    hit = True

                target_result["hits"].append({
                    "shot_num": shot_num + 1,
                    "roll": roll,
                    "modifier": attack_mod,
                    "total": total,
                    "hit": hit,
                    "crit": crit
                })

                if hit:
                    if crit:
                        damage_dice = weapon["damage"]
                        if 'd' in damage_dice:
                            parts = damage_dice.split('d')
                            num_dice = int(parts[0])
                            rest = parts[1]
                            if '+' in rest:
                                die_size, bonus = rest.split('+')
                                damage_dice_crit = f"{num_dice * 2}d{die_size}+{bonus}"
                            else:
                                damage_dice_crit = f"{num_dice * 2}d{rest}"
                        else:
                            damage_dice_crit = damage_dice

                        raw_damage = self._roll_damage(damage_dice_crit)
                        damage_dice_used = damage_dice_crit
                    else:
                        raw_damage = self._roll_damage(weapon["damage"])
                        damage_dice_used = weapon["damage"]

                    pen = weapon["pen"]
                    prot = target["prot"]

                    if pen > prot:
                        scaling = "FULL"
                        scaling_pct = 100
                    elif pen <= prot / 2:
                        scaling = "QUARTER"
                        scaling_pct = 25
                    else:
                        scaling = "HALF"
                        scaling_pct = 50

                    final_damage = self._apply_pen_vs_prot(raw_damage, pen, prot)

                    target_result["damage_dealt"] += final_damage
                    target["hp"] -= final_damage
                    total_damage += final_damage

                    target_result["hits"][-1]["damage_dice"] = damage_dice_used
                    target_result["hits"][-1]["raw_damage"] = raw_damage
                    target_result["hits"][-1]["pen"] = pen
                    target_result["hits"][-1]["prot"] = prot
                    target_result["hits"][-1]["scaling"] = scaling
                    target_result["hits"][-1]["scaling_pct"] = scaling_pct
                    target_result["hits"][-1]["final_damage"] = final_damage

            target_result["final_hp"] = target["hp"]

            if target["hp"] <= 0:
                target_result["killed"] = True
                enemies_killed += 1
                total_xp += 25

            results.append(target_result)

        actual_shots = shots_per_target * len(targets)
        ammo_remaining = ammo_available - actual_shots

        return {
            "weapon": weapon_name,
            "fire_mode": "full_auto",
            "shots_fired": actual_shots,
            "ammo_remaining": ammo_remaining,
            "ammo_type": weapon.get("ammo_type"),
            "base_attack": base_attack,
            "is_sharpshooter": is_sharpshooter,
            "targets": results,
            "total_damage": total_damage,
            "enemies_killed": enemies_killed,
            "total_xp": total_xp
        }

    def update_character_after_combat(self, result: Dict):
        """Update character XP and deduct ammo via inventory-system"""
        char_name = self.character.get("name")
        if not char_name:
            raise RuntimeError("Character has no name")

        if result.get("total_xp", 0) > 0:
            self.player_mgr.award_xp(char_name, result["total_xp"])

        ammo_type = result.get("ammo_type")
        shots_fired = result.get("shots_fired", 0)
        if ammo_type and shots_fired > 0:
            self._deduct_ammo(char_name, ammo_type, shots_fired)

    def _deduct_ammo(self, char_name: str, ammo_type: str, quantity: int):
        """Try to deduct ammo via inventory-system module, fall back to manual"""
        import subprocess

        inventory_script = PROJECT_ROOT / "tools" / "dm-inventory.sh"
        if not inventory_script.exists():
            print(f"[AMMO] dm-inventory.sh not found. Deduct manually: {quantity}x {ammo_type}")
            return

        try:
            cmd = [
                "bash", str(inventory_script), "update", char_name,
                "--remove", ammo_type, str(quantity)
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                print(f"[AUTO-AMMO] Deducted {quantity}x {ammo_type}")
            else:
                print(f"[AMMO] Auto-deduct failed: {proc.stderr.strip()}")
                print(f"[AMMO] Deduct manually: {quantity}x {ammo_type}")
        except Exception as e:
            print(f"[AMMO] Auto-deduct error: {e}")
            print(f"[AMMO] Deduct manually: {quantity}x {ammo_type}")


def format_combat_output(result: Dict) -> str:
    """Format combat result as beautiful output"""
    lines = []
    lines.append("=" * 68)
    lines.append("  FIREARMS COMBAT RESOLVER")
    lines.append("=" * 68)
    lines.append(f"Weapon: {result['weapon']}")
    lines.append(f"Base Attack: +{result['base_attack']}" +
                 (" (Стрелок subclass)" if result['is_sharpshooter'] else ""))
    lines.append(f"Shots Fired: {result['shots_fired']}")
    lines.append(f"Ammo Remaining: {result['ammo_remaining']}")
    lines.append("")
    lines.append("-" * 68)
    lines.append("TARGET RESULTS:")
    lines.append("-" * 68)

    for target in result['targets']:
        lines.append("")
        lines.append(f"{target['name']} (AC {target['ac']}, HP {target['initial_hp']}, PROT {target['prot']})")

        hits = [h for h in target['hits'] if h['hit']]
        crits = [h for h in hits if h['crit']]
        lines.append(f"  Shots: {target['shots']} | Hits: {len(hits)} " +
                     (f"(including {len(crits)} CRITS!)" if crits else ""))
        lines.append("")

        for i, shot in enumerate(target['hits'], 1):
            roll_d20 = shot['roll']
            modifier = shot['modifier']
            total = shot['total']

            if shot['crit']:
                result_str = f"⚔ CRIT! ({roll_d20}+{modifier}={total} vs AC {target['ac']})"
            elif shot['hit']:
                result_str = f"✓ HIT ({roll_d20}+{modifier}={total} vs AC {target['ac']})"
            else:
                result_str = f"✗ MISS ({roll_d20}+{modifier}={total} vs AC {target['ac']})"

            lines.append(f"  Shot #{i}: {result_str}")

            if shot['hit'] and 'final_damage' in shot:
                dmg_dice = shot.get('damage_dice', '?')
                raw_dmg = shot.get('raw_damage', 0)
                pen = shot.get('pen', 0)
                prot = shot.get('prot', 0)
                scaling = shot.get('scaling', 'UNKNOWN')
                final_dmg = shot.get('final_damage', 0)

                lines.append(f"    Damage: {dmg_dice} = {raw_dmg} raw → PEN {pen} vs PROT {prot} = {scaling} → {final_dmg} HP")

        lines.append("")
        if target['damage_dealt'] > 0:
            lines.append(f"  Total Damage Dealt: {target['damage_dealt']} HP")

        if target['killed']:
            overkill = abs(target['final_hp'])
            lines.append(f"  Status: 💀 KILLED (overkill: -{overkill})")
        else:
            lines.append(f"  HP: {target['final_hp']}/{target['initial_hp']}")

    lines.append("")
    lines.append("-" * 68)
    lines.append("SUMMARY:")
    lines.append("-" * 68)
    lines.append(f"Total Damage: {result['total_damage']} HP")
    lines.append(f"Enemies Killed: {result['enemies_killed']}/{len(result['targets'])}")
    lines.append(f"XP Gained: +{result['total_xp']}")
    lines.append("=" * 68)

    return "\n".join(lines)


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(description="Firearms Combat Resolver")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    resolve_parser = subparsers.add_parser('resolve', help='Resolve firearms combat')
    resolve_parser.add_argument('--attacker', required=True, help='Attacker name')
    resolve_parser.add_argument('--weapon', required=True, help='Weapon name')
    resolve_parser.add_argument('--fire-mode', required=True, choices=['single', 'burst', 'full_auto'])
    resolve_parser.add_argument('--ammo', type=int, required=True, help='Available ammo')
    resolve_parser.add_argument('--targets', nargs='+', help='Targets as Name:AC:HP:PROT')
    resolve_parser.add_argument('--enemy-type', help='Enemy type from campaign_rules')
    resolve_parser.add_argument('--enemy-count', type=int, help='Number of enemies')
    resolve_parser.add_argument('--test', action='store_true', help='Test mode: show results but DO NOT update inventory/XP')

    args = parser.parse_args()

    if args.command != 'resolve':
        parser.print_help()
        sys.exit(1)

    try:
        resolver = FirearmsCombatResolver()

        targets = []
        if args.targets:
            for target_str in args.targets:
                parts = target_str.split(':')
                if len(parts) != 4:
                    print(f"[ERROR] Invalid target format: {target_str}", file=sys.stderr)
                    print("Expected: Name:AC:HP:PROT", file=sys.stderr)
                    sys.exit(1)

                targets.append({
                    "name": parts[0],
                    "ac": int(parts[1]),
                    "hp": int(parts[2]),
                    "prot": int(parts[3])
                })
        elif args.enemy_type and args.enemy_count:
            print("[ERROR] --enemy-type not yet implemented", file=sys.stderr)
            sys.exit(1)
        else:
            print("[ERROR] Must specify either --targets or --enemy-type + --enemy-count", file=sys.stderr)
            sys.exit(1)

        if args.fire_mode == 'full_auto':
            result = resolver.resolve_full_auto(args.weapon, args.ammo, targets)
        elif args.fire_mode == 'single':
            result = resolver.resolve_single(args.weapon, args.ammo, targets)
        elif args.fire_mode == 'burst':
            result = resolver.resolve_burst(args.weapon, args.ammo, targets)

        print(format_combat_output(result))

        if args.test:
            print("\n" + "=" * 68)
            print("  🧪 TEST MODE - NO CHANGES APPLIED")
            print("=" * 68)
            print(f"Would update character XP: +{result['total_xp']}")
            print(f"Would deduct ammo: {result['shots_fired']}x {result.get('ammo_type', '?')}")
        else:
            resolver.update_character_after_combat(result)
            print(f"\n[AUTO-PERSIST] XP: +{result['total_xp']}")

    except RuntimeError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
