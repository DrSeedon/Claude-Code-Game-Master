#!/bin/bash
# custom-stats middleware for dm-consequence.sh
# Handles: add ... --hours N (timed consequences with trigger_hours)

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_dir="$MODULE_DIR"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

if [ "$1" = "--help" ]; then
    echo "  add <description> <trigger> --hours <N>  Add timed consequence"
    exit 1
fi

ACTION="$1"

[ "$ACTION" != "add" ] && exit 1

HAS_HOURS=false
for arg in "$@"; do
    [ "$arg" = "--hours" ] && HAS_HOURS=true && break
done

[ "$HAS_HOURS" = false ] && exit 1

shift  # remove 'add'

DESC="${1:-}"
TRIGGER="${2:-}"

if [ -z "$DESC" ] || [ -z "$TRIGGER" ]; then
    echo "[ERROR] Usage: dm-consequence.sh add <description> <trigger> --hours <N>" >&2
    exit 1
fi
shift 2

HOURS_VAL=""
while [ $# -gt 0 ]; do
    if [ "$1" = "--hours" ]; then
        HOURS_VAL="$2"
        shift 2
    else
        shift
    fi
done

if [ -z "$HOURS_VAL" ]; then
    echo "[ERROR] --hours requires a numeric value" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
uv run python - "$DESC" "$TRIGGER" "$HOURS_VAL" <<'PYEOF'
import sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path("lib")))
from json_ops import JsonOperations
from campaign_manager import CampaignManager

desc = sys.argv[1]
trigger = sys.argv[2]
hours = float(sys.argv[3])

campaign_dir = CampaignManager().get_active_campaign_dir()
if not campaign_dir:
    print("[ERROR] No active campaign", file=sys.stderr)
    sys.exit(1)

json_ops = JsonOperations(str(campaign_dir))
data = json_ops.load_json("consequences.json")
if not isinstance(data, dict) or 'active' not in data:
    data = {'active': [], 'resolved': []}

consequence_id = str(uuid.uuid4())[:8]
consequence = {
    'id': consequence_id,
    'consequence': desc,
    'trigger': trigger,
    'trigger_hours': hours,
    'hours_elapsed': 0,
    'created': json_ops.get_timestamp()
}

data['active'].append(consequence)

if json_ops.save_json("consequences.json", data):
    print(f"[SUCCESS] Added timed consequence [{consequence_id}]: {desc} (triggers: {trigger}, after {hours}h)")
else:
    print("[ERROR] Failed to save consequences.json", file=sys.stderr)
    sys.exit(1)
PYEOF
