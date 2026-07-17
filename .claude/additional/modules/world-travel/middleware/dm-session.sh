#!/usr/bin/env bash
# world-travel middleware for dm-session.sh
# Handles move: navigation calc + auto encounter check

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Find project root
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$MODULE_DIR")"

if [ "$1" = "--help" ]; then
    echo "  move <location> [--speed-multiplier X]  Move with distance/time + encounter check"
    exit 64
fi

# Auto-resolve: if player is on compound, move to entry point
if [ "$1" = "start" ] || [ "$1" = "context" ]; then
    HIERARCHY_PY="$MODULE_DIR/lib/hierarchy_manager.py"
    if [ -f "$HIERARCHY_PY" ]; then
        RESOLVE_OUT=$(uv run python "$HIERARCHY_PY" resolve 2>/dev/null)
        RESOLVED=$(echo "$RESOLVE_OUT" | uv run python -c "import sys,json; d=json.load(sys.stdin); print(d.get('resolved', False))" 2>/dev/null)
        if [ "$RESOLVED" = "True" ]; then
            NEW_LOC=$(echo "$RESOLVE_OUT" | uv run python -c "import sys,json; d=json.load(sys.stdin); print(d.get('location',''))" 2>/dev/null)
            echo "[HIERARCHY] Auto-resolved player to entry point: $NEW_LOC"
        fi
    fi
    exit 64  # continue to core handler
fi

[ "$1" = "move" ] || exit 64

shift  # remove 'move'
DESTINATION="$1"

shift
SPEED_MULTIPLIER="1.0"
if [ "$1" = "--speed-multiplier" ]; then
    SPEED_MULTIPLIER="$2"
fi

# One adapter owns hierarchy, vehicle, and overland movement semantics.
uv run python "$MODULE_DIR/lib/movement_adapter.py" \
    "$DESTINATION" \
    --speed-multiplier "$SPEED_MULTIPLIER"
exit $?
