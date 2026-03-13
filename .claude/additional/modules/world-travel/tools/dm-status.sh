#!/usr/bin/env bash
# Module status for session start: full world-travel dump

_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
LOCATIONS="$CAMPAIGN_DIR/locations.json"
OVERVIEW="$CAMPAIGN_DIR/campaign-overview.json"
TRAVEL_DATA="$CAMPAIGN_DIR/module-data/world-travel.json"

[ -f "$LOCATIONS" ] || exit 0

uv run python - "$LOCATIONS" "$OVERVIEW" "$TRAVEL_DATA" << 'PYEOF'
import json, sys, os

loc_path, ov_path, travel_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(loc_path) as f:
    locs = json.load(f)
with open(ov_path) as f:
    ov = json.load(f)

if not isinstance(locs, dict):
    sys.exit(0)

player_pos = ov.get("player_position", {})
current = player_pos.get("current_location", ov.get("current_location", "?"))
loc_stack = player_pos.get("location_stack", [])
prev = player_pos.get("previous_location", "?")

world_locs = []
compounds = []
interiors = []
for name, data in locs.items():
    loc_type = data.get("type", "world")
    if loc_type == "compound":
        compounds.append(name)
    elif loc_type == "interior":
        interiors.append(name)
    else:
        world_locs.append(name)

enc_info = {}
try:
    with open(travel_path) as f:
        td = json.load(f)
    enc_info = td.get("encounter_system", {})
except Exception:
    pass

enc_enabled = enc_info.get("enabled", False)
enc_dc = enc_info.get("base_dc", "?")
time_mods = enc_info.get("time_dc_modifiers", {})

print("🗺️ WORLD TRAVEL")
print(f"  📍 Current: {current}")
if loc_stack:
    print(f"  📍 Stack: {' > '.join(loc_stack)}")
print(f"  ← Previous: {prev}")
print()

print(f"  Locations: {len(locs)} total ({len(world_locs)} world, {len(compounds)} compounds, {len(interiors)} interiors)")

cur_data = locs.get(current, {})
conns = cur_data.get("connections", [])
if conns:
    print(f"  Connections from {current}:")
    for c in conns:
        to = c.get("to", "?")
        dist = c.get("distance_meters", "?")
        terrain = c.get("terrain", "?")
        if isinstance(dist, (int, float)) and dist >= 1000:
            dist_str = f"{dist/1000:.1f}km"
        else:
            dist_str = f"{dist}m"
        print(f"    → {to} ({dist_str}, {terrain})")

print()
enc_str = "enabled" if enc_enabled else "disabled"
print(f"  Encounters: {enc_str} (base DC {enc_dc})")
if time_mods:
    mods_str = ", ".join(f"{k}: {v:+d}" if v != 0 else f"{k}: 0" for k, v in time_mods.items())
    print(f"  Time modifiers: {mods_str}")
PYEOF
