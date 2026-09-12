#!/usr/bin/env python3
"""Migrate a half-graph campaign: module-data inventory/firearms → WorldGraph.

Use when world.json is already schema v2 but inventory/weapons still live only in
module-data/inventory-system.json (pre-embedded inventory era).

Example:
  uv run python tools/migrate_half_graph_campaign.py clone-wars --dry-run
  uv run python tools/migrate_half_graph_campaign.py clone-wars
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "lib"))

from world_graph import WorldGraph  # noqa: E402
from json_ops import JsonOperations  # noqa: E402


# Default ammo labels used by clone-wars / SW-style module-data dumps
DEFAULT_AMMO = {
    "DC-15A": "Заряд DC-15A",
    "DC-15S": "Заряд DC-15S",
    "DC-17": "Заряд DC-17",
    "Z-6": "Заряд Z-6",
    "E-5": "Заряд E-5",
    "E-60R": "Ракета E-60R",
}

STARCRAFT_STYLE_FIRE_MODES = {
    "single": {
        "attacks": 1,
        "ammo": 1,
        "penalty": 0,
        "duration_seconds": 0,
        "max_salvos_per_target": 1,
        "max_salvos_total": 1,
        "penalty_per_salvo": 0,
    },
    "burst": {
        "duration_seconds": 1,
        "max_salvos_per_target": 3,
        "max_salvos_total": 3,
        "penalty_per_salvo": -2,
        "penalty_per_salvo_sharpshooter": -1,
        "max_hits_per_salvo": 3,
        "hit_margin_per_extra_bullet": 5,
    },
    "full_auto": {
        "duration_seconds": 3,
        "max_salvos_per_target": 6,
        "max_salvos_total": 12,
        "penalty_per_salvo": -2,
        "penalty_per_salvo_sharpshooter": -1,
        "max_hits_per_salvo": 3,
        "hit_margin_per_extra_bullet": 5,
    },
}

# Template droids for SW firearms campaigns (creature nodes for auto-combat)
DEFAULT_CREATURES = [
    {
        "id": "creature:b1-battle-droid",
        "name": "B1 Battle Droid",
        "data": {
            "hp": 14,
            "ac": 12,
            "prot": 1,
            "attack_bonus": 3,
            "damage": "2d6",
            "pen": 2,
            "speed": 30,
            "xp": 50,
            "source_module": "firearms-combat",
            "notes": "Standard CIS infantry droid",
        },
    },
    {
        "id": "creature:b2-super-battle-droid",
        "name": "B2 Super Battle Droid",
        "data": {
            "hp": 32,
            "ac": 16,
            "prot": 6,
            "attack_bonus": 5,
            "damage": "2d8+2",
            "pen": 3,
            "speed": 25,
            "xp": 200,
            "source_module": "firearms-combat",
            "notes": "Heavy CIS infantry",
        },
    },
    {
        "id": "creature:droideka",
        "name": "Droideka",
        "data": {
            "hp": 40,
            "ac": 17,
            "prot": 7,
            "attack_bonus": 6,
            "damage": "2d8+2",
            "pen": 4,
            "speed": 20,
            "xp": 450,
            "source_module": "firearms-combat",
            "notes": "Shielded destroyer droid",
        },
    },
    {
        "id": "creature:aat",
        "name": "AAT Tank",
        "data": {
            "hp": 80,
            "ac": 18,
            "prot": 8,
            "attack_bonus": 7,
            "damage": "3d10+4",
            "pen": 6,
            "speed": 40,
            "xp": 1100,
            "source_module": "firearms-combat",
            "notes": "Armored Assault Tank — mass-combat preferred for full crew",
        },
    },
]


def _slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9а-яё]+", "-", s, flags=re.I)
    s = re.sub(r"-+", "-", s).strip("-")
    # ASCII-ish for weapon ids: keep latin already present
    s = re.sub(r"[^a-z0-9-]+", "", s)
    return s or "item"


def _weapon_id(name: str) -> str:
    # Prefer stable latin codes like DC-15A
    clean = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return f"weapon:{clean}"


def _armor_id(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9а-яё]+", "-", name, flags=re.I).strip("-").lower()
    clean = re.sub(r"[^a-z0-9-]+", "", clean)
    return f"armor:{clean or 'armor'}"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _find_npc_id(world: dict, name: str) -> str | None:
    for nid, node in world["nodes"].items():
        if node.get("type") == "npc" and node.get("name") == name:
            return nid
    return None


def _find_location_id(world: dict, name: str) -> str | None:
    for nid, node in world["nodes"].items():
        if node.get("type") == "location" and node.get("name") == name:
            return nid
    return None


def _set_at(world: dict, entity_id: str, location_id: str) -> None:
    world["edges"] = [
        e
        for e in world["edges"]
        if not (e.get("type") == "at" and e.get("from") == entity_id)
    ]
    world["edges"].append({"from": entity_id, "to": location_id, "type": "at"})


def migrate_campaign(campaign_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "campaign": campaign_dir.name,
        "dry_run": dry_run,
        "steps": [],
        "warnings": [],
        "errors": [],
    }

    world_path = campaign_dir / "world.json"
    overview_path = campaign_dir / "campaign-overview.json"
    if not world_path.exists():
        report["errors"].append("world.json missing")
        return report

    world = json.loads(world_path.read_text(encoding="utf-8"))
    overview = _load_json(overview_path, {})
    md = campaign_dir / "module-data"
    inv_player = _load_json(md / "inventory-system.json", {})
    inv_party = _load_json(md / "inventory-party.json", {})
    firearms = _load_json(md / "firearms-combat.json", {})

    player = world["nodes"].get("player:active")
    if not player:
        report["errors"].append("player:active missing")
        return report
    pdata = player.setdefault("data", {})

    # --- 1) money ---
    gold = pdata.get("gold", 0)
    money = pdata.get("money")
    if money is None or money == 0:
        if isinstance(gold, (int, float)) and gold:
            pdata["money"] = int(gold)
            report["steps"].append(f"money set from gold → {pdata['money']}")
        else:
            pdata.setdefault("money", 0)
            report["steps"].append("money defaulted to 0")
    else:
        report["steps"].append(f"money already {money}")

    mods = overview.get("modules") or {}
    if isinstance(mods, list):
        firearms_active = "firearms-combat" in mods
    elif isinstance(mods, dict):
        firearms_active = bool(mods.get("firearms-combat"))
    else:
        firearms_active = False

    # --- 2) abilities alias for firearms module ---
    stats = pdata.get("stats") or {}
    if firearms_active and stats and not pdata.get("abilities"):
        pdata["abilities"] = dict(stats)
        report["steps"].append("abilities copied from stats (firearms attack bonus)")
    level = int(pdata.get("level") or 1)
    if firearms_active and "proficiency_bonus" not in pdata:
        # 5e: L1-4 → +2, L5-8 → +3, ...
        pdata["proficiency_bonus"] = 2 + (max(1, level) - 1) // 4
        report["steps"].append(f"proficiency_bonus={pdata['proficiency_bonus']}")

    # --- 3) player inventory embed ---
    if inv_player and not player.get("inventory"):
        player["inventory"] = {
            "stackable": deepcopy(inv_player.get("stackable") or {}),
            "unique": list(inv_player.get("unique") or []),
        }
        report["steps"].append(
            f"player inventory embedded "
            f"({len(player['inventory']['stackable'])} stackable, "
            f"{len(player['inventory']['unique'])} unique)"
        )
    elif player.get("inventory"):
        report["steps"].append("player inventory already present — left as-is")
    else:
        report["warnings"].append("no module-data/inventory-system.json and no node inventory")

    # --- 4) party inventories ---
    party_moved = 0
    for name, inv in (inv_party or {}).items():
        nid = _find_npc_id(world, name)
        if not nid:
            report["warnings"].append(f"party inventory name not found as NPC: {name}")
            continue
        node = world["nodes"][nid]
        if node.get("inventory"):
            report["steps"].append(f"NPC inventory already present: {name}")
            continue
        node["inventory"] = {
            "stackable": deepcopy(inv.get("stackable") or {}),
            "unique": list(inv.get("unique") or []),
        }
        party_moved += 1
    report["steps"].append(f"NPC inventories embedded: {party_moved}")

    # --- 5) weapon + armor nodes from firearms config ---
    weapons_cfg = firearms.get("weapons") or {} if firearms_active else {}
    armor_cfg = firearms.get("armor") or {} if firearms_active else {}
    ammo_map = dict(DEFAULT_AMMO)

    weapons_added = 0
    for wname, wstats in weapons_cfg.items():
        wid = _weapon_id(wname)
        if wid in world["nodes"]:
            continue
        data = {
            "damage": wstats.get("damage"),
            "pen": wstats.get("pen", 0),
            "rpm": wstats.get("rpm", 60),
            "magazine": wstats.get("magazine", 1),
            "weapon_type": wstats.get("type") or wstats.get("weapon_type") or "firearm",
            "ammo_type": ammo_map.get(wname) or wstats.get("ammo_type") or f"Ammo {wname}",
            "allowed_fire_modes": ["single", "burst", "full_auto"]
            if (wstats.get("rpm") or 0) >= 200
            else ["single", "burst"]
            if (wstats.get("rpm") or 0) >= 60
            else ["single"],
            "source_module": "firearms-combat",
        }
        # pistols: single only is fine but allow burst lightly
        if data["weapon_type"] == "pistol":
            data["allowed_fire_modes"] = ["single", "burst"]
        if data["weapon_type"] == "launcher":
            data["allowed_fire_modes"] = ["single"]
        world["nodes"][wid] = {"type": "weapon", "name": wname, "data": data}
        weapons_added += 1
    report["steps"].append(f"weapon nodes added: {weapons_added}")

    armor_added = 0
    for aname, astats in armor_cfg.items():
        if aname.lower().startswith("без"):
            continue
        aid = _armor_id(aname)
        if aid in world["nodes"]:
            continue
        world["nodes"][aid] = {
            "type": "armor",
            "name": aname,
            "data": {
                "ac": astats.get("ac", 10),
                "prot": astats.get("prot", 0),
                "source_module": "firearms-combat",
            },
        }
        armor_added += 1
    report["steps"].append(f"armor nodes added: {armor_added}")

    # --- 6) player equipment from inventory uniques + config ---
    if firearms_active and weapons_cfg and not pdata.get("equipment"):
        equipped_weapons = []
        prefer = list(weapons_cfg.keys())[:4]
        for wname in prefer:
            wid = _weapon_id(wname)
            node = world["nodes"].get(wid)
            if not node:
                continue
            d = node["data"]
            equipped_weapons.append(
                {
                    "id": wid,
                    "name": node["name"],
                    "damage": d.get("damage"),
                    "pen": d.get("pen"),
                    "rpm": d.get("rpm"),
                    "magazine": d.get("magazine"),
                    "ammo_type": d.get("ammo_type"),
                }
            )
            if len(equipped_weapons) >= 2:
                break
        armor_eq = None
        for aid, node in world["nodes"].items():
            if node.get("type") != "armor":
                continue
            armor_eq = {
                "id": aid,
                "name": node["name"],
                "ac": node["data"].get("ac"),
                "prot": node["data"].get("prot"),
            }
            break
        items = []
        for u in (player.get("inventory") or {}).get("unique") or []:
            if isinstance(u, str):
                items.append(u.split("[")[0].strip())
        pdata["equipment"] = {
            "armor": armor_eq,
            "weapons": equipped_weapons,
            "items": items[:8],
        }
        if armor_eq and armor_eq.get("ac"):
            pdata["ac"] = armor_eq["ac"]
        report["steps"].append(
            f"equipment set: weapons={[w['name'] for w in equipped_weapons]}, "
            f"armor={armor_eq['name'] if armor_eq else None}"
        )
    elif pdata.get("equipment"):
        report["steps"].append("equipment already present — left as-is")
    else:
        report["steps"].append("equipment skipped (no firearms weapons to equip)")

    # --- 7) creatures (SW templates only for clone-wars-style weapon names) ---
    creatures_added = 0
    sw_weapon_hint = any(
        re.search(r"\b(DC-\d|E-\d|Z-6|blaster|AAT)\b", str(name), re.I)
        for name in weapons_cfg
    )
    if firearms_active and weapons_cfg and sw_weapon_hint:
        for c in DEFAULT_CREATURES:
            if c["id"] in world["nodes"]:
                continue
            world["nodes"][c["id"]] = {
                "type": "creature",
                "name": c["name"],
                "data": deepcopy(c["data"]),
            }
            creatures_added += 1
        report["steps"].append(f"SW creature templates added: {creatures_added}")
    else:
        report["steps"].append(
            "creature templates skipped (need SW-style firearms weapon names)"
        )

    # --- 8) relocate party to current overview location ---
    pos = overview.get("player_position") or {}
    current = pos.get("current_location")
    loc_id = _find_location_id(world, current) if current else None
    if loc_id:
        party_ids = [
            nid
            for nid, n in world["nodes"].items()
            if n.get("type") == "npc" and (n.get("data") or {}).get("is_party_member")
        ]
        # also player has no at edge usually — set party only
        moved = 0
        for nid in party_ids:
            _set_at(world, nid, loc_id)
            moved += 1
        # Ahsoka/Wolffe if is_party_member already covered
        report["steps"].append(f"party at edges → {current} ({moved} NPCs)")
    else:
        report["warnings"].append(f"could not resolve current_location: {current}")

    # --- 9) overview modern fields ---
    overview.setdefault("schema_version", 2)
    overview.setdefault("play_mode", "interactive")
    overview.setdefault(
        "cinematic_visuals",
        {
            "enabled": False,
            "frequency": "occasional",
            "aspect_ratio": "16:9",
            "presentation": "game-loading-screen",
        },
    )
    if not overview.get("currency"):
        if firearms_active:
            overview["currency"] = {
                "base": "credit",
                "denominations": [
                    {"id": "credit", "name": "кредит", "symbol": "₡", "rate": 1}
                ],
            }
            report["steps"].append("overview.currency = credits")
        else:
            overview["currency"] = {
                "base": "copper",
                "denominations": [
                    {"id": "copper", "name": "copper", "symbol": "c", "rate": 1},
                    {"id": "silver", "name": "silver", "symbol": "s", "rate": 10},
                    {"id": "gold", "name": "gold", "symbol": "g", "rate": 100},
                ],
            }
            report["steps"].append("overview.currency = D&D copper/silver/gold")
    overview.setdefault("calendar", {})
    # normalize time fields: time_of_day was misused as clock
    tod = overview.get("time_of_day")
    if isinstance(tod, str) and re.match(r"^\d{1,2}:\d{2}", tod):
        overview["precise_time"] = tod
        hour = int(tod.split(":")[0])
        if 5 <= hour < 12:
            overview["time_of_day"] = "Morning"
        elif 12 <= hour < 17:
            overview["time_of_day"] = "Afternoon"
        elif 17 <= hour < 21:
            overview["time_of_day"] = "Evening"
        else:
            overview["time_of_day"] = "Night"
        report["steps"].append(
            f"time_of_day normalized: clock {overview['precise_time']} → {overview['time_of_day']}"
        )
    report["steps"].append("overview play_mode/cinematic defaults ensured")

    # --- 10) firearms config fire_modes upgrade ---
    firearms_changed = False
    if firearms_active and (md / "firearms-combat.json").exists():
        fm = firearms.get("fire_modes") or {}
        needs_fm = "single" not in fm or "duration_seconds" not in (fm.get("full_auto") or {})
        if needs_fm:
            firearms["fire_modes"] = deepcopy(STARCRAFT_STYLE_FIRE_MODES)
            firearms_changed = True
            report["steps"].append(
                "firearms-combat.json fire_modes upgraded to duration/salvo schema"
            )
        else:
            report["steps"].append("firearms fire_modes already modern")
        for wname, wstats in (firearms.get("weapons") or {}).items():
            if "ammo_type" not in wstats:
                wstats["ammo_type"] = ammo_map.get(wname, f"Ammo {wname}")
                firearms_changed = True
    else:
        report["steps"].append("firearms config skipped (module off or missing file)")

    # meta revision bump
    meta = world.setdefault("meta", {"version": 2, "schema": "graph", "revision": 0})
    meta["version"] = 2
    meta["schema"] = "graph"
    meta["revision"] = int(meta.get("revision") or 0) + 1
    meta["half_graph_migrated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if dry_run:
        report["steps"].append("DRY RUN — no files written")
        return report

    # Write world via WorldGraph transaction (lock + atomic replace + revision)
    graph = WorldGraph(campaign_dir)
    with graph.transaction() as w:
        w.clear()
        w.update(world)

    ops = JsonOperations(str(campaign_dir))
    with ops.transaction("campaign-overview.json", default={}) as o:
        o.clear()
        o.update(overview)

    # firearms module-data (only rewrite when we actually changed it)
    firearms_path = md / "firearms-combat.json"
    if firearms_active and firearms_path.exists() and firearms_changed:
        firearms_path.write_text(
            json.dumps(firearms, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # archive legacy inventory dumps (do not delete originals yet — copy for audit)
    archive = md / "archived-pre-embed"
    archive.mkdir(parents=True, exist_ok=True)
    for fname in ("inventory-system.json", "inventory-party.json"):
        src = md / fname
        if src.exists():
            dest = archive / f"{fname}.migrated"
            if not dest.exists():
                shutil.copy2(src, dest)
            report["steps"].append(f"archived {fname} → {dest.relative_to(campaign_dir)}")

    report["steps"].append("world.json + overview written")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("campaign", help="Campaign folder name under world-state/campaigns/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--world-state",
        default=str(PROJECT_ROOT / "world-state"),
        help="world-state root",
    )
    args = ap.parse_args()
    campaign_dir = Path(args.world_state) / "campaigns" / args.campaign
    if not campaign_dir.is_dir():
        print(f"Campaign not found: {campaign_dir}", file=sys.stderr)
        return 2
    report = migrate_campaign(campaign_dir, dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
