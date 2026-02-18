#!/bin/bash
# coordinate-navigation middleware for dm-location.sh
# Handles: add --from, connect --terrain/--distance, decide, routes, block, unblock

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ACTION="$1"
shift

case "$ACTION" in
    decide|routes|block|unblock)
        exec bash "$MODULE_DIR/tools/dm-navigation.sh" "$ACTION" "$@"
        ;;
    add)
        for arg in "$@"; do
            if [ "$arg" = "--from" ]; then
                exec bash "$MODULE_DIR/tools/dm-navigation.sh" add "$@"
            fi
        done
        exit 1
        ;;
    connect)
        for arg in "$@"; do
            if [ "$arg" = "--terrain" ] || [ "$arg" = "--distance" ]; then
                exec bash "$MODULE_DIR/tools/dm-navigation.sh" connect "$@"
            fi
        done
        exit 1
        ;;
esac

exit 1  # not ours
