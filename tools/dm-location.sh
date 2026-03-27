#!/bin/bash
# dm-location.sh - Location management (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-location.sh <action> [args]"
    echo ""
    echo "Actions:"
    echo "  add <name> [desc]              - Add new location"
    echo "  connect <from> <to> [path]     - Connect two locations"
    echo "  describe <name> <description>  - Set location description"
    echo "  get <name>                     - Get location info"
    echo "  show <name>                    - Show location info"
    echo "  list                           - List all locations"
    echo "  connections <name>             - Show location connections"
    echo ""
    echo "Examples:"
    echo "  dm-location.sh add \"Volcano Temple\" \"Ancient obsidian structure\""
    echo "  dm-location.sh connect \"Village\" \"Volcano Temple\" \"rocky path\""
    echo "  dm-location.sh describe \"Volcano Temple\" \"Ancient obsidian structure\""
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-location.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    add)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-location.sh add <name> [desc]"
            exit 1
        fi
        NAME="$1"
        DESC="${2:-}"
        if [ -n "$DESC" ]; then
            $WG location-create "$NAME" --desc "$DESC"
        else
            $WG location-create "$NAME"
        fi
        ;;

    connect)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-location.sh connect <from> <to> [path]"
            exit 1
        fi
        FROM="$1"
        TO="$2"
        PATH_TYPE="${3:-traveled}"
        $WG location-connect "$FROM" "$TO" --path "$PATH_TYPE"
        ;;

    describe)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-location.sh describe <name> <description>"
            exit 1
        fi
        LOC_ID=$($PYTHON_CMD -c "
import sys; sys.path.insert(0,'$LIB_DIR')
from world_graph import WorldGraph
g = WorldGraph()
nid = g._resolve_id('$1', 'location')
print(nid or '')
" 2>/dev/null)
        if [ -z "$LOC_ID" ]; then echo "Error: Location '$1' not found"; exit 1; fi
        $WG update-node "$LOC_ID" --data "{\"description\": \"$2\"}"
        ;;

    get|show)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-location.sh $ACTION <name>"
            exit 1
        fi
        $WG location-show "$1"
        ;;

    list)
        $WG location-list
        ;;

    connections)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-location.sh connections <name>"
            exit 1
        fi
        $WG neighbors "$1" --type connected
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, connect, describe, get, show, list, connections"
        dispatch_middleware_help "dm-location.sh"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-location.sh" "$ACTION" "$@"
exit $CORE_RC
