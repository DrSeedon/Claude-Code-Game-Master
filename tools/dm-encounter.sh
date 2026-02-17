#!/bin/bash
# dm-encounter.sh - Encounter system wrapper (points to module)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_TOOL="$SCRIPT_DIR/../.claude/modules/encounter-system/tools/dm-encounter.sh"

if [ ! -f "$MODULE_TOOL" ]; then
    echo "[ERROR] Encounter system module not found at: $MODULE_TOOL"
    echo "[INFO] This feature has been modularized."
    exit 1
fi

# Pass all arguments to module tool
exec bash "$MODULE_TOOL" "$@"
