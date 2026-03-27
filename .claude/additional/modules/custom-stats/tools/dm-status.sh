#!/usr/bin/env bash
# Module status for session start: full custom-stats dump

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
MODULE_DATA="$CAMPAIGN_DIR/module-data/custom-stats.json"
CHAR_FILE="$CAMPAIGN_DIR/character.json"

[ -f "$MODULE_DATA" ] || exit 0

uv run python - "$MODULE_DATA" "$CHAR_FILE" << 'PYEOF'
import json, sys
from pathlib import Path

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

C = "\033[36m"; B = "\033[1m"; RS = "\033[0m"; DM = "\033[2m"
G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"

game_date = md.get("game_date")
cal_date_str = ""
if game_date:
    _project = next((p for p in Path(md_path).parents if (p / ".git").exists()), None)
    if _project:
        sys.path.insert(0, str(_project))
        _campaign = Path(md_path).parent.parent
        try:
            from lib.calendar import load_config as _load_cal, format_date as _fmt_date, weekday as _wd
            _cal = _load_cal(_campaign)
            _d_str = _fmt_date(game_date, _cal)
            _w_str = _wd(game_date, _cal)
            cal_date_str = f"  📅 {Y}{_w_str}{RS}, {_d_str}" if _w_str else f"  📅 {_d_str}"
        except Exception:
            pass

print(f"{B}📊 CUSTOM STATS{RS}")
print(f"  ⏰ Game Clock: {C}{precise_time}{RS}")
if cal_date_str:
    print(cal_date_str)
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

    def fmt_r(v):
        if v == 0: return "0"
        if abs(v) < 0.1: return f"{v*24:+.1f}/d"
        return f"{v:+.1f}/h"
    eff = per_h + mod
    rate_str = fmt_r(eff)
    if sleep_r is not None:
        rate_str += f" (sleep: {fmt_r(sleep_r)})"

    pct = (cur - mn) / (mx - mn) * 100 if mx > mn else 0
    bar_len = 20
    filled = int(pct / 100 * bar_len)
    bar_color = G if pct < 30 else Y if pct < 60 else R
    bar = f"{bar_color}{'█' * filled}{DM}{'░' * (bar_len - filled)}{RS}"

    print(f"  {name:12s} {bar} {C}{int(cur):>3}{RS}/{mx}  rate: {DM}{rate_str}{RS}")

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
