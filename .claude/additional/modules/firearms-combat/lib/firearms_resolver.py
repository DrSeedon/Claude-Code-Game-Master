#!/usr/bin/env python3
"""
Firearms Combat Resolver — standalone module for modern/STALKER firearms mechanics.

Reads character, weapon, XP, and ammunition state from the campaign WorldGraph.
DM (Claude) calls this via dm-combat.sh for firearms combat resolution.
"""

import argparse
import json
import random
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.campaign_manager import CampaignManager
from lib.world_graph import WorldGraph

from lib.module_data import ModuleDataManager

MODULE_ID = "firearms-combat"

XP_THRESHOLDS = (
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000,
    305000, 355000,
)


class WorldGraphProgression:
    """Load the active player and apply D&D-compatible XP progression."""

    def __init__(self, world_graph: WorldGraph, player_id: str = "player:active"):
        self.world_graph = world_graph
        self.player_id = player_id

    def get_character(self) -> Dict[str, Any]:
        node = self.world_graph.get_node(self.player_id)
        if not node or node.get("type") != "player":
            raise RuntimeError("Active player node 'player:active' not found in world.json")

        character = deepcopy(node.get("data", {}))
        character["name"] = node.get("name", character.get("name", "Player"))
        return character

    def award_xp(self, amount: int) -> Dict[str, Any]:
        character = self.get_character()
        current_level = int(character.get("level", 1))
        if not 1 <= current_level <= 20:
            raise ValueError(f"Invalid player level: {current_level}")

        xp = character.get("xp", 0)
        if isinstance(xp, int):
            xp = {
                "current": xp,
                "next_level": (
                    XP_THRESHOLDS[current_level]
                    if current_level < 20
                    else xp
                ),
            }
        elif isinstance(xp, dict):
            xp = deepcopy(xp)
            xp["current"] = int(xp.get("current", 0))
        else:
            xp = {"current": 0, "next_level": XP_THRESHOLDS[1]}

        xp["current"] += amount
        current_xp = xp["current"]
        new_level = current_level
        while new_level < 20 and current_xp >= XP_THRESHOLDS[new_level]:
            new_level += 1

        leveled_up = new_level > current_level
        next_threshold = XP_THRESHOLDS[new_level] if new_level < 20 else current_xp
        xp["next_level"] = next_threshold

        if not self.world_graph.update_node(
            self.player_id,
            {"data": {"xp": xp, "level": new_level}},
        ):
            return {"success": False}

        name = character["name"]
        if leveled_up:
            print(f"LEVEL_UP {name} gained {amount} XP and leveled up to Level {new_level}!")
        else:
            print(f"XP_GAIN {name} gained {amount} XP!")
        print(f"XP: {current_xp}/{next_threshold if new_level < 20 else 'MAX'}")

        return {
            "success": True,
            "name": name,
            "xp_gained": amount,
            "current_xp": current_xp,
            "next_level_xp": next_threshold if new_level < 20 else "MAX",
            "level_up": leveled_up,
            "old_level": current_level,
            "new_level": new_level,
        }


class FirearmsCombatResolver:
    """Resolves firearms combat with automatic attack/damage calculation"""

    def __init__(self, world_state_dir: str = "world-state"):
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

        if self.campaign_dir is None:
            raise RuntimeError("No active campaign.")

        self.module_data_mgr = ModuleDataManager(self.campaign_dir)
        self.world_graph = WorldGraph(self.campaign_dir)
        self.progression = WorldGraphProgression(self.world_graph)
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
        """Load the active character from the canonical WorldGraph player node."""
        return self.progression.get_character()

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

    @staticmethod
    def _validate_fire_mode(weapon: Dict, mode: str):
        allowed = weapon.get("allowed_fire_modes")
        if allowed and mode not in allowed:
            raise ValueError(
                f"Fire mode '{mode}' is not available for this weapon. "
                f"Allowed: {', '.join(allowed)}"
            )

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
        if self._is_sharpshooter():
            subclass_bonus = 2

        return dex_mod + prof_bonus + subclass_bonus

    def _is_sharpshooter(self) -> bool:
        """Check if character has Стрелок subclass"""
        return self.character.get("subclass") in {"Sharpshooter", "Стрелок"}

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

    def _calculate_rounds_for_duration(self, rpm: int, duration_seconds: float) -> int:
        """Calculate physical rounds fired while the trigger is held."""
        if rpm <= 0 or duration_seconds <= 0:
            return 0
        return max(1, int((rpm / 60) * duration_seconds))

    def _rounds_to_fire(self, weapon: Dict, ammo_available: int, duration_seconds: float) -> int:
        planned = self._calculate_rounds_for_duration(
            int(weapon["rpm"]), duration_seconds
        )
        magazine = int(weapon.get("magazine", ammo_available))
        return max(0, min(ammo_available, magazine, planned))

    @staticmethod
    def _distribute(total: int, buckets: int) -> List[int]:
        if buckets <= 0:
            return []
        base, remainder = divmod(total, buckets)
        return [base + (1 if index < remainder else 0) for index in range(buckets)]

    def _allocate_salvos(
        self,
        rounds_by_target: List[int],
        max_per_target: int,
        max_total: int,
    ) -> List[int]:
        """Allocate a bounded number of attack rolls across targets."""
        counts = [0] * len(rounds_by_target)
        limits = [min(rounds, max_per_target) for rounds in rounds_by_target]
        budget = min(max_total, sum(limits))

        while budget > 0:
            progressed = False
            for index, limit in enumerate(limits):
                if counts[index] >= limit:
                    continue
                counts[index] += 1
                budget -= 1
                progressed = True
                if budget == 0:
                    break
            if not progressed:
                break

        return counts

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
        self._validate_fire_mode(weapon, "single")
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
            "rounds_allocated": 1,
            "salvos": 1,
            "bullets_hit": 1 if hit else 0,
            "hits": [{
                "shot_num": 1, "roll": roll, "modifier": base_attack,
                "total": total, "hit": hit, "crit": crit,
                "rounds_in_salvo": 1,
                "bullets_hit": 1 if hit else 0,
                "crit_bullets": 1 if crit else 0,
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

        magazine = int(weapon.get("magazine", ammo_available))
        magazine_remaining = min(ammo_available, magazine) - 1
        return {
            "weapon": weapon_name,
            "fire_mode": "single",
            "shots_fired": 1,
            "duration_seconds": 0,
            "salvos_fired": 1,
            "bullets_hit": 1 if hit else 0,
            "ammo_remaining": ammo_available - 1,
            "magazine_remaining": magazine_remaining,
            "reload_required": magazine_remaining == 0,
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
        return self._resolve_automatic(
            weapon_name,
            ammo_available,
            targets[:1],
            mode="burst",
        )

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
            "duration_seconds": 0,
            "salvos_fired": 0,
            "bullets_hit": 0,
            "ammo_remaining": ammo,
            "magazine_remaining": 0,
            "reload_required": ammo == 0,
            "ammo_type": None,
            "base_attack": 0,
            "is_sharpshooter": False,
            "targets": [],
            "total_damage": 0,
            "enemies_killed": 0,
            "total_xp": 0
        }

    def _resolve_automatic(
        self,
        weapon_name: str,
        ammo_available: int,
        targets: List[Dict],
        mode: str,
    ) -> Dict:
        if not targets:
            raise ValueError("Automatic fire requires at least one target")

        weapon = self._get_weapon_stats(weapon_name)
        self._validate_fire_mode(weapon, mode)
        fire_mode = self._get_fire_mode_config(mode)
        default_duration = 1 if mode == "burst" else 3
        duration_seconds = float(fire_mode.get("duration_seconds", default_duration))
        shots_fired = self._rounds_to_fire(weapon, ammo_available, duration_seconds)
        if shots_fired == 0:
            return self._empty_result(weapon_name, 0, ammo_available, targets)

        rounds_by_target = self._distribute(shots_fired, len(targets))
        default_max_salvos = 3 if mode == "burst" else 6
        max_salvos_per_target = int(
            fire_mode.get("max_salvos_per_target", default_max_salvos)
        )
        max_salvos_total = int(
            fire_mode.get(
                "max_salvos_total",
                max_salvos_per_target * len(targets),
            )
        )
        salvos_by_target = self._allocate_salvos(
            rounds_by_target,
            max_salvos_per_target,
            max_salvos_total,
        )

        base_attack = self._get_attack_bonus()
        is_sharpshooter = self._is_sharpshooter()

        if is_sharpshooter:
            penalty_per_salvo = fire_mode.get(
                "penalty_per_salvo_sharpshooter",
                fire_mode.get("penalty_per_shot_sharpshooter", -1),
            )
        else:
            penalty_per_salvo = fire_mode.get(
                "penalty_per_salvo",
                fire_mode.get("penalty_per_shot", -2),
            )

        max_hits_per_salvo = int(fire_mode.get("max_hits_per_salvo", 3))
        margin_per_extra = int(fire_mode.get("hit_margin_per_extra_bullet", 5))
        natural_20_hits = int(fire_mode.get("natural_20_hits", 2))

        results = []
        total_damage = 0
        total_bullets_hit = 0
        enemies_killed = 0
        total_xp = 0

        for target, rounds_allocated, salvo_count in zip(
            targets, rounds_by_target, salvos_by_target
        ):
            target_result = {
                "name": target["name"],
                "ac": target["ac"],
                "initial_hp": target["hp"],
                "prot": target["prot"],
                "shots": rounds_allocated,
                "rounds_allocated": rounds_allocated,
                "salvos": salvo_count,
                "bullets_hit": 0,
                "hits": [],
                "damage_dealt": 0,
                "final_hp": target["hp"],
                "killed": False
            }

            rounds_per_salvo = self._distribute(rounds_allocated, salvo_count)
            for salvo_index, rounds_in_salvo in enumerate(rounds_per_salvo):
                penalty = salvo_index * penalty_per_salvo
                attack_mod = base_attack + penalty
                roll = self._roll_d20()
                total = roll + attack_mod
                hit = roll == 20 or (roll != 1 and total >= target["ac"])

                if not hit:
                    bullets_hit = 0
                    crit_bullets = 0
                elif roll == 20:
                    bullets_hit = min(
                        rounds_in_salvo,
                        natural_20_hits,
                        max_hits_per_salvo,
                    )
                    crit_bullets = 1
                else:
                    margin = max(0, total - target["ac"])
                    bullets_hit = min(
                        rounds_in_salvo,
                        max_hits_per_salvo,
                        1 + margin // max(1, margin_per_extra),
                    )
                    crit_bullets = 0

                salvo_data = {
                    "shot_num": salvo_index + 1,
                    "salvo_num": salvo_index + 1,
                    "rounds_in_salvo": rounds_in_salvo,
                    "roll": roll,
                    "modifier": attack_mod,
                    "total": total,
                    "hit": hit,
                    "crit": crit_bullets > 0,
                    "bullets_hit": bullets_hit,
                    "crit_bullets": crit_bullets,
                    "bullet_damage": [],
                }

                if bullets_hit:
                    pen = weapon["pen"]
                    prot = target["prot"]
                    scaling, scaling_pct = self._get_scaling_label(pen, prot)
                    raw_damage_total = 0
                    final_damage_total = 0

                    for bullet_index in range(bullets_hit):
                        critical = bullet_index < crit_bullets
                        damage_dice = (
                            self._double_dice(weapon["damage"])
                            if critical
                            else weapon["damage"]
                        )
                        raw_damage = self._roll_damage(damage_dice)
                        final_damage = self._apply_pen_vs_prot(raw_damage, pen, prot)
                        raw_damage_total += raw_damage
                        final_damage_total += final_damage
                        salvo_data["bullet_damage"].append({
                            "critical": critical,
                            "damage_dice": damage_dice,
                            "raw_damage": raw_damage,
                            "final_damage": final_damage,
                        })

                    target["hp"] -= final_damage_total
                    target_result["damage_dealt"] += final_damage_total
                    target_result["bullets_hit"] += bullets_hit
                    total_damage += final_damage_total
                    total_bullets_hit += bullets_hit

                    salvo_data.update({
                        "damage_dice": weapon["damage"],
                        "raw_damage": raw_damage_total,
                        "pen": pen,
                        "prot": prot,
                        "scaling": scaling,
                        "scaling_pct": scaling_pct,
                        "final_damage": final_damage_total,
                    })

                target_result["hits"].append(salvo_data)

            target_result["final_hp"] = target["hp"]

            if target["hp"] <= 0:
                target_result["killed"] = True
                enemies_killed += 1
                total_xp += 25

            results.append(target_result)

        magazine = int(weapon.get("magazine", ammo_available))
        magazine_remaining = min(ammo_available, magazine) - shots_fired
        return {
            "weapon": weapon_name,
            "fire_mode": mode,
            "shots_fired": shots_fired,
            "duration_seconds": duration_seconds,
            "salvos_fired": sum(salvos_by_target),
            "bullets_hit": total_bullets_hit,
            "ammo_remaining": ammo_available - shots_fired,
            "magazine_remaining": magazine_remaining,
            "reload_required": magazine_remaining == 0,
            "ammo_type": weapon.get("ammo_type"),
            "base_attack": base_attack,
            "is_sharpshooter": is_sharpshooter,
            "targets": results,
            "total_damage": total_damage,
            "enemies_killed": enemies_killed,
            "total_xp": total_xp
        }

    def resolve_full_auto(
        self,
        weapon_name: str,
        ammo_available: int,
        targets: List[Dict]
    ) -> Dict:
        return self._resolve_automatic(
            weapon_name,
            ammo_available,
            targets,
            mode="full_auto",
        )

    def update_character_after_combat(self, result: Dict):
        """Persist earned XP and physical ammunition to WorldGraph."""
        ammo_type = result.get("ammo_type")
        shots_fired = result.get("shots_fired", 0)
        with self.world_graph.transaction():
            if result.get("total_xp", 0) > 0:
                xp_result = self.progression.award_xp(result["total_xp"])
                if not xp_result.get("success"):
                    raise RuntimeError("Failed to persist player XP")

            if ammo_type and shots_fired > 0:
                if not self._deduct_ammo(ammo_type, shots_fired):
                    raise RuntimeError("Failed to persist ammunition use")

        self.character = self._load_character()

    def _deduct_ammo(self, ammo_type: str, quantity: int) -> bool:
        """Deduct rounds from the canonical active-player inventory."""
        if self.world_graph.inventory_remove("player:active", ammo_type, quantity):
            print(f"[AUTO-AMMO] Deducted {quantity}x {ammo_type}")
            return True
        print(f"[AMMO] WorldGraph deduction failed: {quantity}x {ammo_type}")
        return False


def format_combat_output(result: Dict) -> str:
    """Format combat result as beautiful output"""
    lines = []
    lines.append("=" * 68)
    lines.append("  FIREARMS COMBAT RESOLVER")
    lines.append("=" * 68)
    lines.append(f"Weapon: {result['weapon']}")
    lines.append(f"Base Attack: +{result['base_attack']}" +
                 (" (Стрелок subclass)" if result['is_sharpshooter'] else ""))
    lines.append(f"Rounds Fired: {result['shots_fired']}")
    lines.append(f"Salvos Resolved: {result.get('salvos_fired', 0)}")
    lines.append(f"Bullets Hit: {result.get('bullets_hit', 0)}")
    if result.get("duration_seconds"):
        lines.append(f"Trigger Time: {result['duration_seconds']:g}s")
    lines.append(f"Total Ammo Remaining: {result['ammo_remaining']}")
    lines.append(f"Magazine Remaining: {result.get('magazine_remaining', 0)}")
    if result.get("reload_required"):
        lines.append("Reload Required: YES")
    lines.append("")
    lines.append("-" * 68)
    lines.append("TARGET RESULTS:")
    lines.append("-" * 68)

    for target in result['targets']:
        lines.append("")
        lines.append(f"{target['name']} (AC {target['ac']}, HP {target['initial_hp']}, PROT {target['prot']})")

        hits = [h for h in target['hits'] if h['hit']]
        crits = [h for h in hits if h['crit']]
        lines.append(
            f"  Rounds: {target.get('rounds_allocated', target['shots'])} | "
            f"Salvos: {target.get('salvos', len(target['hits']))} | "
            f"Bullets hit: {target.get('bullets_hit', len(hits))}" +
            (f" (including {len(crits)} critical salvo)" if crits else "")
        )
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

            rounds_in_salvo = shot.get("rounds_in_salvo", 1)
            bullets_hit = shot.get("bullets_hit", 1 if shot["hit"] else 0)
            lines.append(
                f"  Salvo #{i} ({rounds_in_salvo} rounds): {result_str}; "
                f"{bullets_hit} bullet(s) hit"
            )

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

    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
