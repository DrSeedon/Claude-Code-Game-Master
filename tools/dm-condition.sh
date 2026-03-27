#!/bin/bash
# dm-condition.sh - Player character condition tracking (delegates to world_graph.py)
# Interface: dm-condition.sh add/remove/check <name> <condition>

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 2 ]; then
    echo "Usage: dm-condition.sh <action> <character_name> [condition]"
    echo ""
    echo "Actions:"
    echo "  add <name> <condition>    - Add condition to character"
    echo "  remove <name> <condition> - Remove condition from character"
    echo "  check <name>              - Show current conditions"
    echo ""
    echo "Examples:"
    echo "  dm-condition.sh add Tandy poisoned"
    echo "  dm-condition.sh remove Tandy poisoned"
    echo "  dm-condition.sh check Tandy"
    exit 1
fi

require_active_campaign

ACTION="$1"
NAME="$2"
CONDITION="$3"

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    add)
        if [ -z "$CONDITION" ]; then
            echo "Error: Condition name required for add"
            exit 1
        fi
        $WG player-condition add "$CONDITION"
        ;;
    remove)
        if [ -z "$CONDITION" ]; then
            echo "Error: Condition name required for remove"
            exit 1
        fi
        $WG player-condition remove "$CONDITION"
        ;;
    check)
        $WG player-condition list
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, remove, check"
        exit 1
        ;;
esac

exit $?
