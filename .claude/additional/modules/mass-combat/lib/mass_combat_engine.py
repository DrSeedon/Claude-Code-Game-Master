#!/usr/bin/env python3
"""Mass Combat Engine — individual unit tracking for large-scale battles."""

import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class C:
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRED = "\033[91m"
    BGREEN = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN = "\033[96m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @staticmethod
    def c(text, *codes):
        return "".join(codes) + str(text) + C.RST

    @staticmethod
    def hp_color(hp, max_hp):
        pct = hp / max_hp if max_hp else 0
        if pct > 0.7:
            return C.BGREEN
        elif pct > 0.3:
            return C.BYELLOW
        return C.BRED

    @staticmethod
    def faction_color(faction):
        f = faction.lower()
        if f in ("enemies", "враги"):
            return C.RED
        if f in ("allies", "союзники"):
            return C.BBLUE
        return C.CYAN

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))

from lib.campaign_manager import CampaignManager

sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "infrastructure"))
from module_data import ModuleDataManager

MODULE_ID = "mass-combat"
COMBAT_STATE_FILE = "combat-state.json"


class MassCombatEngine:

    def __init__(self, world_state_dir: str = "world-state"):
        mgr = CampaignManager(world_state_dir)
        self.campaign_dir = mgr.get_active_campaign_dir()
        if not self.campaign_dir:
            raise RuntimeError("No active campaign.")
        module_data_dir = self.campaign_dir / "module-data"
        module_data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = module_data_dir / COMBAT_STATE_FILE
        self.module_data_mgr = ModuleDataManager(self.campaign_dir)
        self.templates = self._load_templates()
        self.state: Dict = {}
        self.test_mode: bool = False

    def _load_templates(self) -> Dict:
        data = self.module_data_mgr.load(MODULE_ID)
        return data.get("unit_templates", {})

    def _load(self) -> Dict:
        if self.state_path.exists():
            with open(self.state_path, 'r', encoding='utf-8') as f:
                self.state = json.load(f)
        else:
            self.state = {}
        return self.state

    def _save(self):
        if self.test_mode:
            return
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    # ── helpers ──

    def _weighted_sample(self, uids: List[str], k: int) -> List[str]:
        pool = list(uids)
        selected = []
        for _ in range(k):
            if not pool:
                break
            weights = [self.state["units"][u].get("weight", 1) for u in pool]
            pick = random.choices(pool, weights=weights, k=1)[0]
            selected.append(pick)
            pool.remove(pick)
        return selected

    def _is_crewed(self, uid: str) -> bool:
        unit_type = self.state["units"][uid].get("type", "")
        tmpl = self.templates.get(unit_type, {})
        return tmpl.get("crewed", False)

    def _has_crew(self, group: str) -> bool:
        grp = self.state["groups"].get(group, {})
        for uid in grp.get("unit_ids", []):
            u = self.state["units"][uid]
            if u["alive"] and not self._is_crewed(uid):
                return True
        return False

    def _get_range(self, uid: str) -> str:
        unit = self.state["units"][uid]
        if "range" in unit:
            return unit["range"]
        unit_type = unit.get("type", "")
        tmpl = self.templates.get(unit_type, {})
        return tmpl.get("range", "ranged")

    @staticmethod
    def _roll_d20() -> int:
        return random.randint(1, 20)

    @staticmethod
    def _roll_damage(notation: str) -> Tuple[List[int], int, int]:
        m = re.match(r'(\d+)d(\d+)([+-]\d+)?', notation)
        if not m:
            return [0], 0, 0
        n, sides, mod_str = int(m.group(1)), int(m.group(2)), m.group(3)
        mod = int(mod_str) if mod_str else 0
        rolls = [random.randint(1, sides) for _ in range(n)]
        return rolls, mod, sum(rolls) + mod

    # ── INIT ──

    def init_battle(self, name: str) -> str:
        if self.state_path.exists():
            self._load()
            if self.state.get("active"):
                return f"[ERROR] Battle '{self.state['name']}' already active. Use 'end' first."

        self.state = {
            "name": name,
            "active": True,
            "round": 0,
            "factions": {},
            "groups": {},
            "units": {},
            "log": []
        }
        self._save()
        return C.c(f"⚔ Battle '{name}' initialized.", C.BOLD, C.BGREEN) + " Add units with 'add' command."

    # ── ADD units ──

    def add_units(
        self,
        faction: str,
        group: str,
        unit_type: str,
        count: int,
        ac: int,
        hp: int,
        atk: int,
        dmg: str,
        names: Optional[List[str]] = None,
        weight: int = 1,
        unit_range: Optional[str] = None
    ) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        if faction not in self.state["factions"]:
            self.state["factions"][faction] = []
        if group not in self.state["factions"][faction]:
            self.state["factions"][faction].append(group)

        if group not in self.state["groups"]:
            self.state["groups"][group] = {
                "faction": faction,
                "unit_ids": [],
                "cover": False
            }

        added = []
        for i in range(count):
            if names and i < len(names):
                uid = names[i]
            else:
                existing = [u for u in self.state["units"] if u.startswith(f"{unit_type}-")]
                next_num = len(existing) + 1
                uid = f"{unit_type}-{next_num:02d}"

            unit_data = {
                "type": unit_type,
                "group": group,
                "faction": faction,
                "ac": ac,
                "hp": hp,
                "max_hp": hp,
                "atk": atk,
                "dmg": dmg,
                "weight": weight,
                "alive": True,
                "cover": False,
                "conditions": []
            }
            if unit_range:
                unit_data["range"] = unit_range
            self.state["units"][uid] = unit_data
            self.state["groups"][group]["unit_ids"].append(uid)
            added.append(uid)

        self._save()
        fc = C.faction_color(faction)
        return C.c("+", C.BOLD, C.BGREEN) + f" {len(added)} {C.c(unit_type, C.BOLD)} added to {C.c(group, fc)} ({faction}): {C.c(', '.join(added), C.DIM)}"

    def add_named(
        self,
        faction: str,
        group: str,
        name: str,
        ac: int,
        hp: int,
        atk: int,
        dmg: str
    ) -> str:
        return self.add_units(faction, group, name, 1, ac, hp, atk, dmg, names=[name])

    def add_from_template(
        self,
        faction: str,
        group: str,
        template_id: str,
        count: int = 1,
        names: Optional[List[str]] = None,
        weight: Optional[int] = None
    ) -> str:
        tmpl = self.templates.get(template_id)
        if not tmpl:
            available = ", ".join(self.templates.keys()) if self.templates else "none"
            return f"[ERROR] Template '{template_id}' not found. Available: {available}"
        w = weight if weight is not None else tmpl.get("weight", 1)
        return self.add_units(
            faction, group, template_id, count,
            tmpl["ac"], tmpl["hp"], tmpl["atk"], tmpl["dmg"], names, w
        )

    def list_templates(self) -> str:
        if not self.templates:
            return "[INFO] No templates in module-data/mass-combat.json"
        lines = [C.c("═══ UNIT TEMPLATES ═══", C.BOLD, C.BYELLOW)]
        for tid, t in self.templates.items():
            tgt = t.get("targeting", "random")
            rng = t.get("range", "ranged")
            notes = t.get("notes", "")
            tgt_c = C.RED if tgt == "aoe" else (C.CYAN if tgt == "aimed" else C.DIM)
            rng_c = C.BRED if rng == "melee" else (C.BMAGENTA if rng == "both" else C.DIM)
            atk_str = C.c(f"+{t['atk']}", C.BYELLOW)
            rng_tag = f" {C.c(rng, rng_c)}" if rng != "ranged" else ""
            lines.append(
                f"  {C.c(tid, C.BOLD):24s} "
                f"AC {C.c(t['ac'], C.BCYAN):>14s} "
                f"HP {C.c(t['hp'], C.BGREEN):>15s} "
                f"ATK {atk_str} "
                f"DMG {C.c(t['dmg'], C.BRED):>16s} "
                f"[{C.c(tgt, tgt_c)}]{rng_tag} {C.c(notes, C.DIM)}"
            )
        return "\n".join(lines)

    # ── ROUND (group attacks) ──

    def round_attack(
        self,
        group: str,
        target_group: Optional[str] = None,
        target_faction: Optional[str] = None,
        count: Optional[int] = None,
        advantage: bool = False,
        disadvantage: bool = False,
        only_type: Optional[str] = None,
        exclude: Optional[List[str]] = None
    ) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        grp = self.state["groups"].get(group)
        if not grp:
            return f"[ERROR] Group '{group}' not found."

        attacker_faction = grp["faction"]

        if not target_group and not target_faction:
            return "[ERROR] Specify --target-group or --target-faction. Units don't shoot across the whole battlefield."

        targets = self._get_targets(attacker_faction, target_group, target_faction)
        if not targets:
            return f"[ERROR] No valid targets found."

        attackers = [
            uid for uid in grp["unit_ids"]
            if self.state["units"][uid]["alive"]
        ]

        if only_type:
            attackers = [u for u in attackers if self.state["units"][u]["type"] == only_type]
        if exclude:
            attackers = [u for u in attackers if u not in exclude]

        if not attackers:
            return f"[ERROR] No alive units in group '{group}'."

        if count is not None:
            attackers = attackers[:count]

        lines = [C.c(f"═══ {group} ({len(attackers)} units) ═══", C.BOLD, C.BYELLOW)]
        total_hits = 0
        total_dmg = 0
        kills = 0

        has_crew = self._has_crew(group)

        for uid in attackers:
            unit = self.state["units"][uid]

            if self._is_crewed(uid) and not has_crew:
                lines.append(C.c(f"🔇 {uid} — NO CREW, cannot fire!", C.DIM, C.RED))
                continue

            if self._get_range(uid) == "melee":
                same_group_targets = [t for t in targets if self.state["units"][t]["group"] == group]
                if not same_group_targets:
                    lines.append(C.c(f"⚠ {uid} — melee, no enemies in group", C.DIM))
                    continue

            weights = [self.state["units"][t].get("weight", 1) for t in targets]
            target_uid = random.choices(targets, weights=weights, k=1)[0]
            target = self.state["units"][target_uid]

            result = self._resolve_attack(
                uid, unit, target_uid, target,
                advantage=advantage, disadvantage=disadvantage
            )
            lines.append(result["line"])
            total_hits += result["hit"]
            total_dmg += result["damage"]
            if result["killed"]:
                kills += 1
                targets = [t for t in targets if self.state["units"][t]["alive"]]
                if not targets:
                    lines.append(C.c("  ⚠ All targets eliminated!", C.BOLD, C.BGREEN))
                    break

        lines.append(C.c("───", C.DIM))
        hit_c = C.BGREEN if total_hits > 0 else C.RED
        kill_c = C.BRED if kills > 0 else C.DIM
        lines.append(
            f"Hits: {C.c(f'{total_hits}/{len(attackers)}', hit_c)} | "
            f"Damage: {C.c(total_dmg, C.BYELLOW)} | "
            f"Kills: {C.c(kills, kill_c)}"
        )

        self._save()
        return "\n".join(lines)

    # ── ATTACK (single named unit) ──

    def single_attack(
        self,
        attacker_name: str,
        target_names: List[str],
        advantage: bool = False,
        disadvantage: bool = False,
        custom_atk: Optional[int] = None,
        custom_dmg: Optional[str] = None
    ) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        unit = self.state["units"].get(attacker_name)
        if not unit:
            return f"[ERROR] Unit '{attacker_name}' not found."
        if not unit["alive"]:
            return f"[ERROR] Unit '{attacker_name}' is dead."

        atk_range = self._get_range(attacker_name)
        atk_group = unit["group"]

        lines = [C.c(f"═══ {attacker_name} attacks ═══", C.BOLD, C.BYELLOW)]
        total_dmg = 0
        kills = 0

        for tname in target_names:
            target = self.state["units"].get(tname)
            if not target:
                lines.append(C.c(f"  ⚠ Target '{tname}' not found, skipping", C.DIM))
                continue
            if not target["alive"]:
                lines.append(C.c(f"  ⚠ Target '{tname}' already dead, skipping", C.DIM))
                continue
            if atk_range == "melee" and target["group"] != atk_group:
                lines.append(C.c(f"  ⚠ {tname} — out of melee range (different group), skipping", C.RED))
                continue

            atk_override = custom_atk if custom_atk is not None else unit["atk"]
            dmg_override = custom_dmg if custom_dmg is not None else unit["dmg"]

            save_atk, save_dmg = unit["atk"], unit["dmg"]
            unit["atk"] = atk_override
            unit["dmg"] = dmg_override

            result = self._resolve_attack(
                attacker_name, unit, tname, target,
                advantage=advantage, disadvantage=disadvantage
            )
            unit["atk"], unit["dmg"] = save_atk, save_dmg

            lines.append(result["line"])
            total_dmg += result["damage"]
            if result["killed"]:
                kills += 1

        if len(target_names) > 1:
            lines.append(C.c("───", C.DIM))
            kill_c = C.BRED if kills > 0 else C.DIM
            lines.append(f"Total damage: {C.c(total_dmg, C.BYELLOW)} | Kills: {C.c(kills, kill_c)}")

        self._save()
        return "\n".join(lines)

    # ── TURRET / HEAVY WEAPON FIRE ──

    def turret_fire(
        self,
        turret_name: str,
        target_group: str,
        num_targets: Optional[int] = None
    ) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        turret = self.state["units"].get(turret_name)
        if not turret:
            return f"[ERROR] Unit '{turret_name}' not found."
        if not turret["alive"]:
            return f"[ERROR] '{turret_name}' is destroyed."

        turret_group = turret.get("group")
        if turret_group and self._is_crewed(turret_name) and not self._has_crew(turret_group):
            return C.c(f"🔇 {turret_name} — NO CREW alive in group '{turret_group}', cannot fire!", C.RED, C.DIM)

        grp = self.state["groups"].get(target_group)
        if not grp:
            return f"[ERROR] Target group '{target_group}' not found."

        candidates = [
            uid for uid in grp["unit_ids"]
            if self.state["units"][uid]["alive"]
        ]
        if not candidates:
            return f"[ERROR] No alive targets in '{target_group}'."

        tmpl = self.templates.get(turret["type"], {})
        aoe_mode = tmpl.get("aoe_mode", "blast")
        save_type = tmpl.get("aoe_save_type", "DEX")
        save_dc = tmpl.get("aoe_save_dc", 14)
        max_targets = num_targets or tmpl.get("aoe_targets", 3)

        if aoe_mode == "spray":
            return self._spray_fire(turret_name, turret, candidates, max_targets, save_type, save_dc)

        selected = self._weighted_sample(candidates, min(max_targets, len(candidates)))
        return self.aoe_damage(
            turret_name, selected, turret["dmg"],
            save_type=save_type, save_dc=save_dc, half_on_save=True
        )

    def _spray_fire(
        self,
        source_name: str,
        source_unit: Dict,
        candidates: List[str],
        num_shots: int,
        save_type: str,
        save_dc: int
    ) -> str:
        weights = [self.state["units"][u].get("weight", 1) for u in candidates]
        targets = random.choices(candidates, weights=weights, k=num_shots)

        dmg_dice = source_unit['dmg']
        lines = [C.c(f"═══ {source_name}: SPRAY {dmg_dice} ×{num_shots} ═══", C.BOLD, C.BMAGENTA)]
        total_dmg = 0
        kills = 0

        for tgt_uid in targets:
            target = self.state["units"][tgt_uid]
            if not target["alive"]:
                lines.append(C.c(f"  → {tgt_uid}: already dead, wasted shot", C.DIM))
                continue

            rolls, mod, dmg = self._roll_damage(dmg_dice)
            rolls_str = "+".join(str(r) for r in rolls)
            mod_str = f"{mod:+d}" if mod else ""

            save_roll = self._roll_d20()
            if save_roll >= save_dc:
                actual = dmg // 2
                save_str = f" (save {C.c(f'[{save_roll}]', C.BGREEN)} vs DC {save_dc} ✓ → half)"
            else:
                actual = dmg
                save_str = f" (save {C.c(f'[{save_roll}]', C.BRED)} vs DC {save_dc} ✗)"

            old_hp = target["hp"]
            target["hp"] -= actual
            killed = ""
            if target["hp"] <= 0:
                target["alive"] = False
                killed = C.c(" 💀", C.BRED)
                kills += 1

            total_dmg += actual
            hp_c = C.hp_color(max(0, target["hp"]), target["max_hp"])
            lines.append(
                f"  🔫 → {C.c(tgt_uid, C.BOLD)}: [{rolls_str}]{mod_str}={dmg}{save_str}"
                f" → {C.c(actual, C.BYELLOW)} dmg (HP {old_hp}→{C.c(max(0, target['hp']), hp_c)}){killed}"
            )

        lines.append(C.c("───", C.DIM))
        kill_c = C.BRED if kills > 0 else C.DIM
        lines.append(f"Total: {C.c(total_dmg, C.BYELLOW)} dmg | Kills: {C.c(kills, kill_c)}")

        self._save()
        return "\n".join(lines)

    # ── AOE (grenade, force push, etc) ──

    def aoe_damage(
        self,
        source: str,
        target_names: List[str],
        damage_notation: str,
        save_type: Optional[str] = None,
        save_dc: Optional[int] = None,
        half_on_save: bool = True
    ) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        rolls, mod, total = self._roll_damage(damage_notation)
        rolls_str = "+".join(str(r) for r in rolls)
        mod_str = f" {mod:+d}" if mod else ""

        lines = [C.c(f"═══ {source}: AOE {damage_notation} ═══", C.BOLD, C.BRED)]
        lines.append(f"Damage roll: {C.c(f'[{rolls_str}]{mod_str}', C.BYELLOW)} = {C.c(total, C.BOLD, C.BYELLOW)}")

        kills = 0
        for tname in target_names:
            target = self.state["units"].get(tname)
            if not target or not target["alive"]:
                continue

            actual_dmg = total
            save_result = ""

            if save_type and save_dc:
                save_roll = self._roll_d20()
                save_mod = 0
                save_total = save_roll + save_mod
                if save_total >= save_dc:
                    if half_on_save:
                        actual_dmg = total // 2
                    else:
                        actual_dmg = 0
                    save_result = f" (save {C.c(f'[{save_roll}]', C.BGREEN)} vs DC {save_dc} ✓ → {actual_dmg})"
                else:
                    save_result = f" (save {C.c(f'[{save_roll}]', C.BRED)} vs DC {save_dc} ✗ → full)"

            old_hp = target["hp"]
            target["hp"] -= actual_dmg
            killed = ""
            if target["hp"] <= 0:
                target["alive"] = False
                killed = C.c(" 💀", C.BRED)
                kills += 1

            hp_c = C.hp_color(max(0, target["hp"]), target["max_hp"])
            lines.append(f"  {C.c(tname, C.BOLD)}: {C.c(actual_dmg, C.BYELLOW)} dmg → HP {old_hp}→{C.c(max(0, target['hp']), hp_c)}{save_result}{killed}")

        lines.append(C.c("───", C.DIM))
        kill_c = C.BRED if kills > 0 else C.DIM
        lines.append(f"Kills: {C.c(f'{kills}/{len(target_names)}', kill_c)}")

        self._save()
        return "\n".join(lines)

    # ── DAMAGE (direct) ──

    def direct_damage(self, unit_name: str, amount: int) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        unit = self.state["units"].get(unit_name)
        if not unit:
            return f"[ERROR] Unit '{unit_name}' not found."

        old_hp = unit["hp"]
        unit["hp"] -= amount
        killed = ""
        if unit["hp"] <= 0 and unit["alive"]:
            unit["alive"] = False
            killed = C.c(" 💀 KILLED", C.BOLD, C.BRED)

        hp_c = C.hp_color(max(0, unit["hp"]), unit["max_hp"])
        self._save()
        return f"{C.c(unit_name, C.BOLD)}: {C.c(amount, C.BYELLOW)} dmg → HP {old_hp}→{C.c(max(0, unit['hp']), hp_c)}{killed}"

    # ── HEAL ──

    def heal(self, unit_name: str, amount: int) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        unit = self.state["units"].get(unit_name)
        if not unit:
            return f"[ERROR] Unit '{unit_name}' not found."

        old_hp = unit["hp"]
        unit["hp"] = min(unit["hp"] + amount, unit["max_hp"])
        if not unit["alive"] and unit["hp"] > 0:
            unit["alive"] = True

        hp_c = C.hp_color(unit["hp"], unit["max_hp"])
        self._save()
        return f"{C.c(unit_name, C.BOLD)}: {C.c(f'+{amount}', C.BGREEN)} HP → {old_hp}→{C.c(unit['hp'], hp_c)}/{unit['max_hp']}"

    # ── KILL ──

    def kill_unit(self, unit_name: str) -> str:
        self._load()
        unit = self.state["units"].get(unit_name)
        if not unit:
            return f"[ERROR] Unit '{unit_name}' not found."
        unit["hp"] = 0
        unit["alive"] = False
        self._save()
        return C.c(f"💀 {unit_name} killed.", C.BOLD, C.BRED)

    # ── COVER ──

    def set_cover(self, group: str, cover: bool) -> str:
        self._load()
        grp = self.state["groups"].get(group)
        if not grp:
            return f"[ERROR] Group '{group}' not found."

        for uid in grp["unit_ids"]:
            if self.state["units"][uid]["alive"]:
                self.state["units"][uid]["cover"] = cover

        grp["cover"] = cover
        self._save()
        alive = sum(1 for uid in grp["unit_ids"] if self.state["units"][uid]["alive"])
        if cover:
            return C.c(f"🛡 {group} takes cover (+2 AC) ({alive} units)", C.BCYAN)
        return f"🛡 {group} leaves cover ({alive} units)"

    # ── STATUS ──

    def status(self, group: Optional[str] = None) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        battle_name = self.state['name']
        rnd = self.state['round']
        lines = [C.c(f"═══ BATTLE: {battle_name} | Round {rnd} ═══", C.BOLD, C.BYELLOW)]
        lines.append("")

        all_groups = []
        for faction, groups in self.state["factions"].items():
            for grp_name in groups:
                if grp_name not in all_groups:
                    all_groups.append(grp_name)

        for grp_name in all_groups:
            if group and grp_name != group:
                continue
            grp = self.state["groups"][grp_name]
            uids = grp["unit_ids"]

            alive_by_faction = {}
            dead_count = 0
            for uid in uids:
                u = self.state["units"][uid]
                if u["alive"]:
                    f = u["faction"]
                    alive_by_faction[f] = alive_by_faction.get(f, 0) + 1
                else:
                    dead_count += 1

            total_alive = sum(alive_by_faction.values())
            factions_present = set(alive_by_faction.keys())

            if total_alive == 0:
                zone_c = C.DIM
            elif len(factions_present) > 1:
                zone_c = C.BYELLOW
            else:
                f = next(iter(factions_present))
                zone_c = C.faction_color(f)

            cover_tag = C.c(" [COVER +2AC]", C.BCYAN) if grp.get("cover") else ""
            alive_c = C.BGREEN if total_alive == len(uids) else (C.BYELLOW if total_alive > 0 else C.DIM)
            lines.append(f"  {C.c(grp_name, C.BOLD, zone_c)}: {C.c(f'{total_alive}/{len(uids)}', alive_c)} alive{cover_tag}")

            for uid in uids:
                u = self.state["units"][uid]
                fc = C.faction_color(u["faction"])
                if u["alive"]:
                    hp_pct = u["hp"] / u["max_hp"]
                    hp_c = C.hp_color(u["hp"], u["max_hp"])
                    filled = int(hp_pct * 5)
                    bar = C.c("█" * filled, hp_c) + C.c("░" * (5 - filled), C.DIM)
                    cover_mark = C.c(" 🛡", C.BCYAN) if u["cover"] else ""
                    rng = self._get_range(uid)
                    rng_tag = C.c(" ⚔", C.BMAGENTA) if rng == "melee" else ""
                    lines.append(f"    {C.c(uid, C.BOLD, fc)}: HP {C.c(u['hp'], hp_c)}/{u['max_hp']} [{bar}]{cover_mark}{rng_tag}")
                else:
                    lines.append(f"    {C.c(uid, C.DIM)}: 💀")

            if dead_count > 0:
                lines.append(C.c(f"    ({dead_count} dead)", C.DIM))
            lines.append("")

        for faction in self.state["factions"]:
            fc = C.faction_color(faction)
            total = sum(1 for u in self.state["units"].values() if u["faction"] == faction)
            alive_cnt = sum(1 for u in self.state["units"].values() if u["faction"] == faction and u["alive"])
            alive_c = C.BGREEN if alive_cnt == total else (C.BYELLOW if alive_cnt > 0 else C.BRED)
            lines.append(f"{C.c(faction, fc)}: {C.c(f'{alive_cnt}/{total}', alive_c)} alive")

        return "\n".join(lines)

    # ── MOVE ──

    def move_units(self, unit_names: List[str], target_group: str) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        grp = self.state["groups"].get(target_group)
        if not grp:
            return f"[ERROR] Target group '{target_group}' not found."

        lines = []
        for uid in unit_names:
            unit = self.state["units"].get(uid)
            if not unit:
                lines.append(f"  ⚠ '{uid}' not found")
                continue
            if not unit["alive"]:
                lines.append(f"  ⚠ '{uid}' is dead")
                continue

            old_group = unit["group"]
            if old_group == target_group:
                lines.append(f"  ⚠ '{uid}' already in {target_group}")
                continue

            old_grp = self.state["groups"].get(old_group)
            if old_grp and uid in old_grp["unit_ids"]:
                old_grp["unit_ids"].remove(uid)

            grp["unit_ids"].append(uid)
            unit["group"] = target_group
            lines.append(f"  {C.c('→', C.BGREEN)} {C.c(uid, C.BOLD)}: {old_group} → {C.c(target_group, C.BCYAN)} (faction: {unit['faction']})")

        self._save()
        header = C.c(f"═══ MOVE → {target_group} ═══", C.BOLD, C.BCYAN)
        return header + "\n" + "\n".join(lines)

    # ── NEXT ROUND ──

    def next_round(self) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."
        self.state["round"] += 1
        self._save()
        return C.c(f"═══ ROUND {self.state['round']} ═══", C.BOLD, C.BYELLOW)

    # ── END ──

    def end_battle(self) -> str:
        self._load()
        if not self.state.get("active"):
            return "[ERROR] No active battle."

        lines = [C.c(f"═══ BATTLE END: {self.state['name']} ═══", C.BOLD, C.BYELLOW)]
        lines.append("")

        total_xp = 0
        for faction in self.state["factions"]:
            fc = C.faction_color(faction)
            total = sum(1 for u in self.state["units"].values() if u["faction"] == faction)
            dead = sum(1 for u in self.state["units"].values() if u["faction"] == faction and not u["alive"])
            lines.append(f"{C.c(faction, fc)}: {C.c(f'{dead}/{total}', C.BRED if dead > 0 else C.BGREEN)} casualties")

        enemies_killed = sum(
            1 for u in self.state["units"].values()
            if u["faction"] == "enemies" and not u["alive"]
        )
        total_xp = enemies_killed * 25
        lines.append(f"\n{C.c('XP earned:', C.BOLD, C.BGREEN)} {C.c(total_xp, C.BYELLOW)} ({enemies_killed} enemies killed × 25)")

        self.state["active"] = False
        self._save()

        if self.state_path.exists():
            self.state_path.unlink()

        return "\n".join(lines)

    # ── internal ──

    def _get_targets(
        self,
        attacker_faction: str,
        target_group: Optional[str],
        target_faction: Optional[str]
    ) -> List[str]:
        targets = []
        for uid, u in self.state["units"].items():
            if not u["alive"]:
                continue
            if u["faction"] == attacker_faction:
                continue
            if target_group and u["group"] == target_group:
                targets.append(uid)
            elif target_faction and u["faction"] == target_faction:
                targets.append(uid)
            elif not target_group and not target_faction:
                targets.append(uid)
        return targets

    def _resolve_attack(
        self,
        atk_uid: str,
        attacker: Dict,
        def_uid: str,
        defender: Dict,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict:
        ac = defender["ac"]
        if defender.get("cover"):
            ac += 2

        if advantage:
            r1, r2 = self._roll_d20(), self._roll_d20()
            roll = max(r1, r2)
            roll_str = f"[{roll}]({min(r1, r2)})"
        elif disadvantage:
            r1, r2 = self._roll_d20(), self._roll_d20()
            roll = min(r1, r2)
            roll_str = f"[{roll}]({max(r1, r2)})"
        else:
            roll = self._roll_d20()
            roll_str = f"[{roll}]"

        atk_bonus = attacker["atk"]
        total_atk = roll + atk_bonus

        nat20 = roll == 20
        nat1 = roll == 1

        if nat20:
            hit = True
        elif nat1:
            hit = False
        else:
            hit = total_atk >= ac

        damage = 0
        killed = False
        dmg_str = ""

        if hit:
            dmg_notation = attacker["dmg"]
            if nat20:
                m = re.match(r'(\d+)(d\d+.*)', dmg_notation)
                if m:
                    dmg_notation = f"{int(m.group(1)) * 2}{m.group(2)}"

            rolls, mod, damage = self._roll_damage(dmg_notation)
            rolls_s = "+".join(str(r) for r in rolls)
            mod_s = f"{mod:+d}" if mod else ""
            dmg_str = f" → {dmg_notation}=[{rolls_s}]{mod_s}={C.c(damage, C.BYELLOW)} dmg"

            defender["hp"] -= damage
            if defender["hp"] <= 0:
                defender["alive"] = False
                killed = True

        cover_tag = C.c(" (cover)", C.BCYAN) if defender.get("cover") else ""
        hp_after = max(0, defender["hp"])

        if nat20:
            verdict = C.c("⚔ CRIT!", C.BOLD, C.BYELLOW)
        elif nat1:
            verdict = C.c("💀 FUMBLE", C.BOLD, C.RED)
        elif hit:
            verdict = C.c("✓ HIT", C.BGREEN)
        else:
            verdict = C.c("✗ MISS", C.DIM)

        kill_tag = C.c(" 💀", C.BRED) if killed else ""
        hp_c = C.hp_color(hp_after, defender["max_hp"]) if hit else ""
        hp_tag = f" (HP→{C.c(hp_after, hp_c)})" if hit else ""

        roll_c = C.BYELLOW if nat20 else (C.RED if nat1 else C.WHITE)
        line = f"🎲 {C.c(atk_uid, C.BOLD)} → {C.c(def_uid, C.BOLD)}{cover_tag} vs AC {ac}: {C.c(roll_str, roll_c)}+{atk_bonus}={total_atk} — {verdict}{dmg_str}{hp_tag}{kill_tag}"

        return {
            "line": line,
            "hit": 1 if hit else 0,
            "damage": damage,
            "killed": killed
        }


# ── CLI ──

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Mass Combat Engine")
    parser.add_argument("--test", action="store_true", help="Test mode: show results but don't save changes")
    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init")
    p_init.add_argument("name", help="Battle name")

    # add
    p_add = sub.add_parser("add")
    p_add.add_argument("--faction", required=True)
    p_add.add_argument("--group", required=True)
    p_add.add_argument("--template", help="Template ID from module-data")
    p_add.add_argument("--type", dest="unit_type", help="Unit type (when not using template)")
    p_add.add_argument("--count", type=int, default=1)
    p_add.add_argument("--ac", type=int, help="AC (required without template)")
    p_add.add_argument("--hp", type=int, help="HP (required without template)")
    p_add.add_argument("--atk", type=int, help="ATK bonus (required without template)")
    p_add.add_argument("--dmg", help="Damage dice (required without template)")
    p_add.add_argument("--names", nargs="*", help="Custom names for units")
    p_add.add_argument("--weight", type=int, default=None, help="Targeting weight (higher = more likely to be targeted)")
    p_add.add_argument("--range", dest="unit_range", choices=["melee", "ranged", "both"], help="Attack range")

    # templates
    sub.add_parser("templates")

    # round
    p_round = sub.add_parser("round")
    p_round.add_argument("group", help="Attacking group")
    p_round.add_argument("--target-group", help="Specific target group")
    p_round.add_argument("--target-faction", help="Target faction")
    p_round.add_argument("--count", type=int, help="How many units from group attack")
    p_round.add_argument("--type", dest="only_type", help="Only units of this type attack")
    p_round.add_argument("--exclude", nargs="+", help="Exclude these unit names")
    p_round.add_argument("--advantage", action="store_true")
    p_round.add_argument("--disadvantage", action="store_true")

    # attack
    p_atk = sub.add_parser("attack")
    p_atk.add_argument("attacker", help="Unit name")
    p_atk.add_argument("--targets", nargs="+", required=True)
    p_atk.add_argument("--advantage", action="store_true")
    p_atk.add_argument("--disadvantage", action="store_true")
    p_atk.add_argument("--atk", type=int, help="Override attack bonus")
    p_atk.add_argument("--dmg", help="Override damage dice")

    # aoe
    p_aoe = sub.add_parser("aoe")
    p_aoe.add_argument("source", help="Source name (grenade, Force Push, etc)")
    p_aoe.add_argument("--targets", nargs="+", required=True)
    p_aoe.add_argument("--damage", required=True, help="Damage notation")
    p_aoe.add_argument("--save-type", help="Save type (DEX, CON, etc)")
    p_aoe.add_argument("--save-dc", type=int, help="Save DC")
    p_aoe.add_argument("--no-half", action="store_true", help="No damage on save (instead of half)")

    # turret
    p_turret = sub.add_parser("turret")
    p_turret.add_argument("turret_name", help="Turret unit name")
    p_turret.add_argument("--target-group", required=True, help="Target group")
    p_turret.add_argument("--targets", type=int, default=3, help="How many targets to hit (no repeats)")

    # damage
    p_dmg = sub.add_parser("damage")
    p_dmg.add_argument("unit", help="Unit name")
    p_dmg.add_argument("amount", type=int)

    # heal
    p_heal = sub.add_parser("heal")
    p_heal.add_argument("unit", help="Unit name")
    p_heal.add_argument("amount", type=int)

    # kill
    p_kill = sub.add_parser("kill")
    p_kill.add_argument("unit", help="Unit name")

    # cover
    p_cover = sub.add_parser("cover")
    p_cover.add_argument("group", help="Group name")
    p_cover.add_argument("--remove", action="store_true", help="Remove cover")

    # status
    p_status = sub.add_parser("status")
    p_status.add_argument("--group", help="Show specific group only")

    # move
    p_move = sub.add_parser("move")
    p_move.add_argument("units", nargs="+", help="Unit names to move")
    p_move.add_argument("--to", required=True, dest="target_group", help="Target group")

    # next-round
    sub.add_parser("next-round")

    # end
    sub.add_parser("end")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    engine = MassCombatEngine()

    if args.test:
        engine.test_mode = True

    if args.command == "init":
        print(engine.init_battle(args.name))

    elif args.command == "add":
        if args.template:
            print(engine.add_from_template(
                args.faction, args.group, args.template, args.count, args.names,
                weight=args.weight
            ))
        elif args.unit_type and args.ac and args.hp and args.atk and args.dmg:
            print(engine.add_units(
                args.faction, args.group, args.unit_type, args.count,
                args.ac, args.hp, args.atk, args.dmg, args.names,
                weight=args.weight or 1,
                unit_range=args.unit_range
            ))
        else:
            print("[ERROR] Use --template OR (--type --ac --hp --atk --dmg)")
            sys.exit(1)

    elif args.command == "templates":
        print(engine.list_templates())

    elif args.command == "round":
        print(engine.round_attack(
            args.group,
            target_group=args.target_group,
            target_faction=args.target_faction,
            count=args.count,
            advantage=args.advantage,
            disadvantage=args.disadvantage,
            only_type=args.only_type,
            exclude=args.exclude
        ))

    elif args.command == "attack":
        print(engine.single_attack(
            args.attacker, args.targets,
            advantage=args.advantage,
            disadvantage=args.disadvantage,
            custom_atk=args.atk,
            custom_dmg=args.dmg
        ))

    elif args.command == "aoe":
        print(engine.aoe_damage(
            args.source, args.targets, args.damage,
            save_type=args.save_type,
            save_dc=args.save_dc,
            half_on_save=not args.no_half
        ))

    elif args.command == "turret":
        print(engine.turret_fire(
            args.turret_name, args.target_group, args.targets
        ))

    elif args.command == "damage":
        print(engine.direct_damage(args.unit, args.amount))

    elif args.command == "heal":
        print(engine.heal(args.unit, args.amount))

    elif args.command == "kill":
        print(engine.kill_unit(args.unit))

    elif args.command == "cover":
        print(engine.set_cover(args.group, not args.remove))

    elif args.command == "status":
        print(engine.status(group=args.group))

    elif args.command == "move":
        print(engine.move_units(args.units, args.target_group))

    elif args.command == "next-round":
        print(engine.next_round())

    elif args.command == "end":
        print(engine.end_battle())

    if args.test:
        print("\n🧪 TEST MODE — no changes saved")


if __name__ == "__main__":
    main()
