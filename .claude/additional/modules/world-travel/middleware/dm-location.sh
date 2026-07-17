#!/bin/bash
# world-travel middleware for dm-location.sh
# Handles: add --from, connect --terrain/--distance, decide, routes, block, unblock

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$1" = "--help" ]; then
    echo "  add <name> <pos> --from <loc> --bearing <deg> --distance <m> [--terrain <type>]"
    echo "  connect <from> <to> [path] --terrain <type> --distance <m>"
    echo "  decide <from> <to>    - Choose route between locations"
    echo "  routes <from> <to>    - Show all possible routes"
    echo "  block <loc> <from_deg> <to_deg> <reason>"
    echo "  unblock <loc> <from_deg> <to_deg>"
    exit 64
fi

ACTION="$1"
shift

case "$ACTION" in
    decide|routes|block|unblock)
        exec bash "$MODULE_DIR/tools/dm-navigation.sh" "$ACTION" "$@"
        ;;
    add)
        for arg in "$@"; do
            if [ "$arg" = "--from" ]; then
                bash "$MODULE_DIR/tools/dm-navigation.sh" add "$@"
                exit $?
            fi
        done
        exit 64
        ;;
    connect)
        for arg in "$@"; do
            if [ "$arg" = "--terrain" ] || [ "$arg" = "--distance" ]; then
                bash "$MODULE_DIR/tools/dm-navigation.sh" connect "$@"
                exit $?
            fi
        done
        exit 64
        ;;
esac

exit 64  # not ours
