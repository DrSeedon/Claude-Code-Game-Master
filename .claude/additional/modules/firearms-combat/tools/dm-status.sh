#!/usr/bin/env bash
# Module status for session start: full firearms-combat dump

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
FC_DATA="$CAMPAIGN_DIR/module-data/firearms-combat.json"

[ -f "$FC_DATA" ] || exit 0

uv run python - "$FC_DATA" << 'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    d = json.load(f)

cr = d.get("campaign_rules", {})
fs = cr.get("firearms_system", {})
weapons = fs.get("weapons", {})
fire_modes = fs.get("fire_modes", {})
pen_rules = fs.get("penetration_vs_armor", {}).get("rules", {})
armor_sys = cr.get("armor_system", {})
armor_types = armor_sys.get("armor_types", {})
bestiary = cr.get("enemies_modern", {})

skip = {"enabled", "description"}

print("🔫 FIREARMS COMBAT")
print()

if weapons:
    print("  Weapons:")
    for k, w in weapons.items():
        if k in skip:
            continue
        name = w.get("name", k)
        dmg = w.get("damage", "?")
        pen = w.get("pen", "?")
        rpm = w.get("rpm", "?")
        mag = w.get("magazine", "?")
        wtype = w.get("type", "?")
        print(f"    {name:.<35s} {dmg:>8s}  PEN {pen}  RPM {rpm:>4}  mag {mag:>2}  ({wtype})")

if fire_modes:
    print()
    print("  Fire Modes:")
    for k, fm in fire_modes.items():
        desc = fm.get("description", k)
        penalty = fm.get("penalty_per_shot", fm.get("penalty", 0))
        sharp = fm.get("penalty_per_shot_sharpshooter", None)
        sharp_str = f" (sharpshooter: {sharp})" if sharp is not None else ""
        print(f"    {k:.<15s} {desc}  penalty/shot: {penalty}{sharp_str}")

if pen_rules:
    print()
    print("  Penetration vs Armor:")
    for rule_name, rule_desc in pen_rules.items():
        print(f"    {rule_name}: {rule_desc}")

if armor_types:
    print()
    print("  Armor Types:")
    for k, a in armor_types.items():
        if k in skip:
            continue
        name = a.get("name", k)
        ac = a.get("ac_bonus", "?")
        prot = a.get("prot", "?")
        weight = a.get("weight", "?")
        print(f"    {name:.<30s} AC+{ac}  PROT {prot}  ({weight})")

if bestiary:
    print()
    print("  Bestiary:")
    for k, b in bestiary.items():
        if k in skip or k == "description":
            continue
        name = b.get("name", k)
        ac = b.get("ac", "?")
        hp = b.get("hp", "?")
        prot = b.get("prot", "?")
        atk = b.get("attack", "?")
        dmg = b.get("damage", "?")
        cr_val = b.get("cr", "?")
        xp = b.get("xp", "?")
        print(f"    {name:.<30s} AC {ac:>2}  HP {hp:>3}  PROT {prot}  ATK {atk}  DMG {dmg}  CR {cr_val}  XP {xp}")
PYEOF
