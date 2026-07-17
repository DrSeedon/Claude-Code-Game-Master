#!/usr/bin/env bash
# Module status for session start: full firearms-combat dump

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

ACTIVE="${DM_ACTIVE_CAMPAIGN:-$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")}"
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
FC_DATA="$CAMPAIGN_DIR/module-data/firearms-combat.json"
WORLD_DATA="$CAMPAIGN_DIR/world.json"

[ -f "$FC_DATA" ] || exit 0
[ -f "$WORLD_DATA" ] || exit 0

uv run python - "$FC_DATA" "$WORLD_DATA" << 'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    d = json.load(f)
with open(sys.argv[2]) as f:
    world = json.load(f)

fire_modes = d.get("fire_modes", {})
pen_rules = d.get("penetration_vs_armor", {})
nodes = world.get("nodes", {})
weapons = [node for node in nodes.values() if node.get("type") == "weapon"]
armor_types = [node for node in nodes.values() if node.get("type") == "armor"]
bestiary = [node for node in nodes.values() if node.get("type") == "creature"]

skip = {"enabled", "description"}

print("🔫 FIREARMS COMBAT")
print()

if weapons:
    print("  Weapons:")
    for node in weapons:
        name = node.get("name", "Unknown")
        w = node.get("data", {})
        dmg = w.get("damage", "?")
        pen = w.get("pen", "?")
        rpm = w.get("rpm", "?")
        mag = w.get("magazine", "?")
        wtype = w.get("weapon_type", "?")
        print(f"    {name:.<35s} {dmg:>8s}  PEN {pen}  RPM {rpm:>4}  mag {mag:>2}  ({wtype})")

if fire_modes:
    print()
    print("  Fire Modes:")
    for k, fm in fire_modes.items():
        desc = fm.get("description", k)
        duration = fm.get("duration_seconds", 0)
        salvos = fm.get("max_salvos_per_target", fm.get("attacks", 1))
        penalty = fm.get("penalty_per_salvo", fm.get("penalty", 0))
        sharp = fm.get("penalty_per_salvo_sharpshooter", None)
        sharp_str = f" (sharpshooter: {sharp})" if sharp is not None else ""
        print(f"    {k:.<15s} {desc}  {duration}s, max {salvos} salvo(s), recoil {penalty}{sharp_str}")

if pen_rules:
    print()
    print("  Penetration vs Armor:")
    for rule_name, rule_desc in pen_rules.items():
        if isinstance(rule_desc, dict):
            continue
        print(f"    {rule_name}: {rule_desc}")

if armor_types:
    print()
    print("  Armor Types:")
    for node in armor_types:
        name = node.get("name", "Unknown")
        a = node.get("data", {})
        ac = a.get("ac_bonus", "?")
        prot = a.get("prot", "?")
        weight = a.get("weight", "?")
        print(f"    {name:.<30s} AC+{ac}  PROT {prot}  ({weight})")

if bestiary:
    print()
    print("  Bestiary:")
    for node in bestiary:
        name = node.get("name", "Unknown")
        b = node.get("data", {})
        ac = b.get("ac", "?")
        hp = b.get("hp", "?")
        prot = b.get("prot", "?")
        atk = b.get("attack", "?")
        dmg = b.get("damage", "?")
        cr_val = b.get("cr", "?")
        xp = b.get("xp", "?")
        print(f"    {name:.<30s} AC {ac:>2}  HP {hp:>3}  PROT {prot}  ATK {atk}  DMG {dmg}  CR {cr_val}  XP {xp}")
PYEOF
