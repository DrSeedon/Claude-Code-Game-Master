#!/bin/bash
# survival-stats middleware for dm-player.sh
# Handles: custom-stat, custom-stats-list

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$1" = "--help" ]; then
    echo "  custom-stat [name] <stat> [+/-amount]  Get or modify a custom stat"
    echo "  custom-stats-list [name]               List all custom stats"
    exit 1
fi

ACTION="$1"
shift

_dir="$MODULE_DIR"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"

case "$ACTION" in
    custom-stat)
        # custom-stat [char_name] <stat_name> [+/-delta] [--reason "text"]
        # Skip optional character name (first arg that's not a stat/delta)
        STAT_NAME=""
        DELTA=""
        REASON=""
        CHAR_SKIPPED=false
        while [ $# -gt 0 ]; do
            case "$1" in
                --reason) REASON="$2"; shift 2 ;;
                +*|-*) DELTA="$1"; shift ;;
                *)
                    if [ -z "$STAT_NAME" ]; then
                        # Could be char name or stat name — if next arg looks like stat, this is char
                        if [ -n "$2" ] && [ "$2" != "--reason" ] && ! echo "$2" | grep -qE '^[+-]'; then
                            shift  # skip char name
                        else
                            STAT_NAME="$1"; shift
                        fi
                    else
                        shift
                    fi
                    ;;
            esac
        done
        if [ -z "$STAT_NAME" ]; then
            echo "[ERROR] Usage: dm-player.sh custom-stat [name] <stat> [+/-delta] [--reason text]" >&2
            exit 0
        fi
        cd "$PROJECT_ROOT"
        if [ -n "$DELTA" ]; then
            REASON_FLAG=""
            [ -n "$REASON" ] && REASON_FLAG="--reason $REASON"
            uv run python lib/world_graph.py custom-stat "$STAT_NAME" "$DELTA" $REASON_FLAG
        else
            uv run python lib/world_graph.py custom-stat "$STAT_NAME"
        fi
        exit 0
        ;;
    custom-stats-list)
        cd "$PROJECT_ROOT"
        uv run python lib/world_graph.py custom-stat-list
        exit 0
        ;;
esac

exit 1
