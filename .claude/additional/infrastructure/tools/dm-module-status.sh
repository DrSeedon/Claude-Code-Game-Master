#!/usr/bin/env bash
# Collects status from all active modules that have dm-status.sh
# Called at session start to show module state summary

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../common-module.sh"
PROJECT_ROOT="$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

ACTIVE="${DM_ACTIVE_CAMPAIGN:-$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")}"
[ -z "$ACTIVE" ] && exit 0

OVERVIEW="$PROJECT_ROOT/world-state/campaigns/$ACTIVE/campaign-overview.json"
[ -f "$OVERVIEW" ] || exit 0

MODULES_DIR="$PROJECT_ROOT/.claude/additional/modules"

ENABLED=$(uv run python -c "
import json, sys
with open('$OVERVIEW') as f:
    d = json.load(f)
modules = d.get('modules', [])
if isinstance(modules, dict):
    print(*[k for k, enabled in modules.items() if enabled], sep='\n')
elif isinstance(modules, list):
    print(*modules, sep='\n')
" 2>/dev/null)

[ -z "$ENABLED" ] && exit 0

echo "=== MODULE STATUS ==="
echo ""

FOUND=0
while IFS= read -r mod; do
    STATUS_SCRIPT="$MODULES_DIR/$mod/tools/dm-status.sh"
    if [ -f "$STATUS_SCRIPT" ]; then
        OUTPUT=$(bash "$STATUS_SCRIPT" 2>/dev/null)
        if [ -n "$OUTPUT" ]; then
            echo "$OUTPUT"
            FOUND=$((FOUND + 1))
        fi
    fi
done <<< "$ENABLED"

if [ "$FOUND" -eq 0 ]; then
    echo "  (no module status available)"
fi

echo ""
echo "=== END MODULE STATUS ==="
