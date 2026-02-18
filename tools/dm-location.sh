#!/bin/bash
# dm-location.sh - Location management (thin wrapper for location_manager.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-location.sh <action> [args]"
    echo ""
    echo "Actions:"
    echo "  add <name> <position>                - Add new location"
    echo "  add <name> <position> --from <loc> --bearing <deg> --distance <m> [--terrain <type>]"
    echo "                                       - Add with coordinates (requires coordinate-navigation module)"
    echo "  connect <from> <to> [path]           - Connect two locations"
    echo "  connect <from> <to> [path] --terrain <type> --distance <m>"
    echo "                                       - Connect with metadata (requires coordinate-navigation module)"
    echo "  describe <name> <description>        - Set location description"
    echo "  get <name>                           - Get location info"
    echo "  list                                 - List all locations"
    echo "  connections <name>                   - Show location connections"
    echo ""
    echo "Navigation (requires coordinate-navigation module):"
    echo "  decide <from> <to>                   - Decide route between locations"
    echo "  routes <from> <to>                   - Show all possible routes"
    echo "  block <location> <from_deg> <to_deg> <reason> - Block direction range"
    echo "  unblock <location> <from_deg> <to_deg>        - Unblock direction range"
    echo ""
    echo "Examples:"
    echo "  dm-location.sh add \"Volcano Temple\" \"north of village\""
    echo "  dm-location.sh add \"Temple\" \"1km north\" --from \"Village\" --bearing 0 --distance 1000"
    echo "  dm-location.sh connect \"Village\" \"Volcano Temple\" \"rocky path\""
    echo "  dm-location.sh describe \"Volcano Temple\" \"Ancient obsidian structure\""
    echo "  dm-location.sh decide \"Village\" \"Temple\""
    echo "  dm-location.sh block \"Village\" 160 200 \"Steep cliff\""
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-location.sh" "$ACTION" "$@" && exit $?

case "$ACTION" in
    add)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-location.sh add <name> <position>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/location_manager.py" add "$@"
        ;;

    connect)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-location.sh connect <from> <to> [path]"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/location_manager.py" connect "$@"
        ;;

    describe)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-location.sh describe <name> <description>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/location_manager.py" describe "$1" "$2"
        ;;

    get)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-location.sh get <name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/location_manager.py" get "$1"
        ;;

    list)
        echo "Locations"
        echo "========="
        $PYTHON_CMD "$LIB_DIR/location_manager.py" list
        ;;

    connections)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-location.sh connections <name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/location_manager.py" connections "$1"
        ;;

    decide|routes|block|unblock)
        echo "[ERROR] '$ACTION' requires the coordinate-navigation module"
        echo "  Module not found at: .claude/modules/coordinate-navigation"
        exit 1
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, connect, describe, get, list, connections, decide, routes, block, unblock"
        exit 1
        ;;
esac

exit $?
