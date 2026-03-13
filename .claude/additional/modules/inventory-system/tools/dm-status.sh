#!/usr/bin/env bash
# Module status for session start: full inventory dump

_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
INV_DATA="$CAMPAIGN_DIR/module-data/inventory-system.json"
PARTY_DATA="$CAMPAIGN_DIR/module-data/inventory-party.json"
CHAR_FILE="$CAMPAIGN_DIR/character.json"

[ -f "$INV_DATA" ] || exit 0

uv run python - "$INV_DATA" "$CHAR_FILE" "$PARTY_DATA" << 'PYEOF'
import json, sys, re, os

inv_path, char_path, party_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(inv_path) as f:
    inv = json.load(f)
with open(char_path) as f:
    char = json.load(f)

gold = char.get("gold", 0)
name = char.get("name", "?")
hp = char.get("hp", {})
hp_cur = hp.get("current", 0) if isinstance(hp, dict) else hp
hp_max = hp.get("max", 0) if isinstance(hp, dict) else hp
xp = char.get("xp", {})
xp_cur = xp.get("current", 0) if isinstance(xp, dict) else xp
xp_next = xp.get("next_level", 300) if isinstance(xp, dict) else 300
level = char.get("level", 0)

stats = char.get("stats", {})
strength = stats.get("str", char.get("abilities", {}).get("strength", 10))
capacity = strength * 7

stackable = inv.get("stackable", {})
unique = inv.get("unique", [])

def calc_weight(stackable, unique):
    w = 0.0
    for item_name, info in stackable.items():
        if isinstance(info, dict):
            w += info.get("qty", 0) * info.get("weight", 0.5)
        else:
            w += int(info) * 0.5
    for item in unique:
        m = re.search(r'\[(\d+(?:\.\d+)?)к?g?\]', str(item))
        w += float(m.group(1)) if m else 1.0
    return w

total_weight = calc_weight(stackable, unique)

pct = total_weight / capacity if capacity > 0 else 0
if pct <= 1.0:
    status = "Normal"
elif pct <= 1.3:
    status = "Encumbered"
elif pct <= 1.6:
    status = "Heavy"
elif pct <= 2.0:
    status = "Overloaded"
else:
    status = "Immobile"

print(f"🎒 INVENTORY — {name}")
print(f"  HP: {hp_cur}/{hp_max} | LVL: {level} | XP: {xp_cur}/{xp_next} | Gold: {gold}")
print(f"  Weight: {total_weight:.1f}/{capacity} kg ({status})")
print()

if stackable:
    print("  Stackable:")
    for item_name, info in stackable.items():
        if isinstance(info, dict):
            qty = info.get("qty", 0)
            w = info.get("weight", 0.5)
            print(f"    {item_name:.<30s} x{qty}  ({w}kg ea = {qty*w:.1f}kg)")
        else:
            print(f"    {item_name:.<30s} x{info}")

if unique:
    print("  Unique:")
    for item in unique:
        print(f"    • {item}")

if os.path.exists(party_path):
    try:
        with open(party_path) as f:
            party = json.load(f)
        if party:
            print()
            print("  Party Inventories:")
            for pname, pdata in party.items():
                p_stack = pdata.get("stackable", {})
                p_uniq = pdata.get("unique", [])
                p_w = calc_weight(p_stack, p_uniq)
                print(f"    {pname}: {len(p_stack)} stackable, {len(p_uniq)} unique ({p_w:.1f}kg)")
    except Exception:
        pass
PYEOF
