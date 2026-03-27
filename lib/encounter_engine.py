#!/usr/bin/env python3
"""
Encounter Engine — random encounter system for travel.
Checks for encounters when travel time passes (elapsed hours).
Config lives in campaign-overview.json → "encounters" section.
"""

import json
import random
import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from colors import Colors

C = Colors.C
G = Colors.G
R = Colors.R
Y = Colors.Y
B = Colors.B
BR = Colors.BR
BG = Colors.BG
BY = Colors.BY
DM = Colors.DM
RS = Colors.RS


def _find_project_root() -> Path:
    return next(p for p in Path(__file__).parents if (p / ".git").exists())


def _get_active_campaign_dir() -> Optional[Path]:
    root = _find_project_root()
    active_file = root / "world-state" / "active-campaign.txt"
    if not active_file.exists():
        return None
    name = active_file.read_text().strip()
    d = root / "world-state" / "campaigns" / name
    return d if d.exists() else None


def _load_overview(campaign_dir: Path) -> dict:
    f = campaign_dir / "campaign-overview.json"
    if not f.exists():
        return {}
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def _save_overview(campaign_dir: Path, data: dict):
    f = campaign_dir / "campaign-overview.json"
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _load_wiki(campaign_dir: Path) -> dict:
    f = campaign_dir / "wiki.json"
    if not f.exists():
        return {}
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def _weighted_choice(types: dict) -> tuple[str, int]:
    """Pick random category weighted by values. Returns (category, weight)."""
    if not types:
        return ("unknown", 0)
    total = sum(types.values())
    if total <= 0:
        key = random.choice(list(types.keys()))
        return (key, types[key])
    r = random.randint(1, total)
    cumulative = 0
    for category, weight in types.items():
        cumulative += weight
        if r <= cumulative:
            return (category, weight)
    last = list(types.items())[-1]
    return (last[0], last[1])


def _find_creature_by_type(wiki: dict, encounter_type: str) -> Optional[dict]:
    """Find a creature in wiki matching the encounter type by tag or name."""
    type_lower = encounter_type.lower().rstrip("s")
    candidates = []
    for eid, data in wiki.items():
        if not isinstance(data, dict):
            continue
        if data.get("type") != "creature":
            continue
        tags = [t.lower() for t in data.get("tags", [])]
        name_lower = data.get("name", eid).lower()
        if (encounter_type.lower() in tags or
                type_lower in tags or
                type_lower in name_lower or
                encounter_type.lower() in name_lower):
            candidates.append(data)
    if not candidates:
        return None
    chosen = random.choice(candidates)
    return chosen


def check_encounter(elapsed_hours: float, campaign_dir: Path) -> Optional[dict]:
    """
    Check for random encounters during travel.

    Args:
        elapsed_hours: Hours of travel time that passed
        campaign_dir: Path to active campaign directory

    Returns:
        dict with encounter info, or None if no encounter
    """
    if elapsed_hours <= 0:
        return None

    overview = _load_overview(campaign_dir)
    enc_cfg = overview.get("encounters")
    if not enc_cfg:
        return None
    if not enc_cfg.get("enabled", False):
        return None

    chance_per_hour = enc_cfg.get("chance_per_hour", 15)
    min_hours_between = enc_cfg.get("min_hours_between", 2)
    last_enc = enc_cfg.get("last_encounter_time")
    types = enc_cfg.get("types", {})

    if last_enc is not None:
        hours_since_last = float(last_enc)
        remaining_cooldown = min_hours_between - hours_since_last
        if remaining_cooldown > 0:
            effective_start = remaining_cooldown
        else:
            effective_start = 0
        enc_cfg["last_encounter_time"] = max(0, hours_since_last + elapsed_hours - min_hours_between)
    else:
        effective_start = 0
        enc_cfg["last_encounter_time"] = elapsed_hours

    triggered_hour = None
    roll_value = None

    total_hours = int(elapsed_hours) + (1 if elapsed_hours % 1 > 0 else 0)
    for hour in range(1, total_hours + 1):
        if hour <= effective_start:
            continue
        roll = random.randint(1, 100)
        if roll <= chance_per_hour:
            triggered_hour = hour
            roll_value = roll
            enc_cfg["last_encounter_time"] = 0
            break

    overview["encounters"] = enc_cfg
    _save_overview(campaign_dir, overview)

    if triggered_hour is None:
        return None

    category, weight = _weighted_choice(types)
    total_weight = sum(types.values()) if types else 100

    wiki = _load_wiki(campaign_dir)
    creature = _find_creature_by_type(wiki, category)

    return {
        "triggered": True,
        "type": category,
        "weight": weight,
        "total_weight": total_weight,
        "hour": triggered_hour,
        "roll": roll_value,
        "chance": chance_per_hour,
        "creature": creature,
    }


def format_encounter(result: dict) -> str:
    """Format encounter result for CLI display."""
    lines = []
    lines.append(f"\n{BR}⚔ ENCOUNTER at hour {result['hour']} of travel!{RS}")
    lines.append(f"  Type: {B}{result['type']}{RS} {DM}(weight: {result['weight']}/{result['total_weight']}){RS}")
    lines.append(f"  🎲 d100 = {C}{result['roll']}{RS} vs {Y}{result['chance']}%{RS} — {BG}TRIGGERED{RS}")

    creature = result.get("creature")
    if creature:
        m = creature.get("mechanics", {})
        ac = m.get("ac", m.get("AC", "?"))
        hp = m.get("hp", m.get("HP", "?"))
        atk = m.get("attack_bonus", m.get("attack", "?"))
        dmg = m.get("damage", "?")
        name = creature.get("name", result["type"])
        lines.append(f"\n  {B}Creature:{RS} {C}{name}{RS}  AC {ac}  HP {hp}  Attack +{atk}  Dmg {dmg}")
        lines.append(f"  Ready for auto-combat: {DM}dm-roll.sh --target \"{name.lower()}\"{RS}")
    else:
        lines.append(f"\n  {DM}No creature stats in wiki. DM narrates encounter.{RS}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Random encounter checker for travel")
    parser.add_argument("--elapsed", type=float, required=True, help="Hours of travel elapsed")
    parser.add_argument("--campaign-dir", type=str, help="Campaign directory path (auto-detect if omitted)")
    args = parser.parse_args()

    if args.campaign_dir:
        campaign_dir = Path(args.campaign_dir)
    else:
        campaign_dir = _get_active_campaign_dir()
        if not campaign_dir:
            print(f"{BR}[ERROR]{RS} No active campaign found", file=sys.stderr)
            sys.exit(1)

    result = check_encounter(args.elapsed, campaign_dir)
    if result:
        print(format_encounter(result))
    else:
        print(f"  {DM}No encounter during travel ({args.elapsed}h).{RS}")


if __name__ == "__main__":
    main()
