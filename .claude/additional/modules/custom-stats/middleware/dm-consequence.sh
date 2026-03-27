#!/bin/bash
# custom-stats middleware for dm-consequence.sh
# Handles: add ... --hours N (timed consequences with trigger_hours)

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$MODULE_DIR")"

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
uv run python lib/world_graph.py consequence-add "$DESC" "$TRIGGER" --hours "$HOURS_VAL"
