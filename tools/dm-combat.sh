#!/usr/bin/env bash
#
# dm-combat.sh - Firearms Combat Resolver (CORE wrapper)
# Delegates to firearms-combat module
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

MODULE_PATH=".claude/modules/firearms-combat/tools/dm-combat.sh"

if [[ -f "$MODULE_PATH" ]]; then
    bash "$MODULE_PATH" "$@"
else
    echo "[ERROR] Firearms combat module not found at: $MODULE_PATH" >&2
    echo "This campaign may not have firearms support enabled." >&2
    exit 1
fi
