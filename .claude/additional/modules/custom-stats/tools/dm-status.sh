#!/usr/bin/env bash
# Module status for session start: full custom-stats dump

_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
MODULE_DATA="$CAMPAIGN_DIR/module-data/custom-stats.json"
CHAR_FILE="$CAMPAIGN_DIR/character.json"

[ -f "$MODULE_DATA" ] || exit 0

uv run python - "$MODULE_DATA" "$CHAR_FILE" << 'PYEOF'
import json, sys

md_path, char_path = sys.argv[1], sys.argv[2]

with open(md_path) as f:
    md = json.load(f)

if not md.get("enabled", False):
    sys.exit(0)

stats = md.get("character_stats", {})
rules = md.get("rules", [])
consequences = md.get("stat_consequences", {})
precise_time = md.get("precise_time", "?")

effects = []
try:
    with open(char_path) as f:
        char = json.load(f)
    effects = char.get("active_effects", [])
except Exception:
    pass

print("📊 CUSTOM STATS")
print(f"  ⏰ Game Clock: {precise_time}")
print()

for name, info in stats.items():
    if isinstance(info, dict):
        cur = info.get("value", info.get("current", 0))
        mn = info.get("min", 0)
        mx = info.get("max", 100)
        mod = info.get("rate_modifier", 0)
    else:
        cur, mn, mx, mod = info, 0, 100, 0

    rule = next((r for r in rules if r.get("stat") == name), {})
    per_h = rule.get("per_hour", 0)
    sleep_r = rule.get("sleep_rate", None)

    rate_str = f"{per_h:+}/h"
    if sleep_r is not None:
        rate_str += f" (sleep: {sleep_r:+}/h)"
    if mod != 0:
        rate_str += f" [modifier: {mod:+}]"

    pct = (cur - mn) / (mx - mn) * 100 if mx > mn else 0
    bar_len = 20
    filled = int(pct / 100 * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)

    print(f"  {name:12s} {bar} {int(cur):>3}/{mx}  rate: {rate_str}")

if consequences:
    print()
    print("  Thresholds:")
    for cname, cdata in consequences.items():
        cond = cdata.get("condition", {})
        effs = cdata.get("effects", [])
        msg = next((e["text"] for e in effs if e.get("type") == "message"), "")
        dmg = next((f"{e['amount']}/h" for e in effs if e.get("type") == "hp_damage"), "")
        cond_str = f"{cond.get('stat', '?')} {cond.get('operator', '?')} {cond.get('value', '?')}"
        parts = [cond_str]
        if dmg:
            parts.append(f"HP {dmg}")
        if msg:
            parts.append(msg)
        print(f"    ⚠ {cname}: {' → '.join(parts)}")

if effects:
    print()
    print("  Active Effects:")
    for e in effects:
        rem = e.get("remaining_hours", 0)
        eff_list = e.get("effects", [])
        eff_str = ", ".join(f"{x.get('stat','?')} {x.get('rate_bonus', x.get('per_hour', '?')):+}" for x in eff_list)
        print(f"    🎭 {e['name']}: {eff_str} ({rem:.1f}h left)")
else:
    print()
    print("  Active Effects: none")
PYEOF
