#!/usr/bin/env bash
#
# dm-module.sh - Module Management
# List, scan, and manage DM System modules
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Find project root
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../common-module.sh"
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

ACTION="${1:-}"

case "$ACTION" in
    activate)
        MODULE="${2:-}"
        if [ -z "$MODULE" ]; then
            echo "Usage: dm-module.sh activate <module-id>"
            exit 1
        fi
        uv run python .claude/additional/module_loader.py activate --module "$MODULE"
        ;;
    deactivate)
        MODULE="${2:-}"
        if [ -z "$MODULE" ]; then
            echo "Usage: dm-module.sh deactivate <module-id>"
            exit 1
        fi
        uv run python .claude/additional/module_loader.py deactivate --module "$MODULE"
        ;;
    list-verbose)
        uv run python - "$PROJECT_ROOT" <<'PYEOF'
import sys, json, os, glob

root = sys.argv[1]
modules_dir = os.path.join(root, ".claude", "additional", "modules")
active_file = os.path.join(root, "world-state", "active-campaign.txt")
campaign_modules = None
try:
    campaign_name = os.environ.get("DM_ACTIVE_CAMPAIGN", "").strip()
    if not campaign_name:
        with open(active_file) as f:
            campaign_name = f.read().strip()
    overview_path = os.path.join(
        root, "world-state", "campaigns", campaign_name, "campaign-overview.json"
    )
    with open(overview_path) as f:
        configured = json.load(f).get("modules", [])
    if isinstance(configured, list):
        campaign_modules = {module_id: True for module_id in configured}
    elif isinstance(configured, dict):
        campaign_modules = configured
except (OSError, json.JSONDecodeError):
    pass

paths = sorted(glob.glob(os.path.join(modules_dir, "*/module.json")))
for i, path in enumerate(paths, 1):
    with open(path) as f:
        d = json.load(f)

    is_active = (
        bool(campaign_modules.get(d["id"], False))
        if campaign_modules is not None
        else bool(d.get("enabled_by_default", False))
    )

    status = "✅ Active" if is_active else "❌ Inactive"
    default_note = "  ← on by default" if d.get("enabled_by_default") else ""
    tags = ", ".join(d.get("genre_tags", []))
    cases = " / ".join(d.get("use_cases", [])[:3])

    print(f"  [{i}] {status}  {d['id']}")
    print(f"      {d['name']}")
    print(f"      {d['description']}")
    print(f"      Genres: {tags}")
    print(f"      Use cases: {cases}")
    if default_note:
        print(f"     {default_note}")
    print()
PYEOF
        ;;
    *)
        uv run python .claude/additional/module_loader.py "$@"
        ;;
esac
