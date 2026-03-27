#!/bin/bash
# dm-consequence.sh - Consequence tracking (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-consequence.sh <action> [args]"
    echo ""
    echo "Actions:"
    echo "  add <description> <trigger> [--hours N]  - Add new consequence"
    echo "  check                                    - Check all consequences"
    echo "  resolve <id> [resolution]                - Resolve a consequence"
    echo ""
    echo "Examples:"
    echo "  dm-consequence.sh add \"Guards searching for party\" \"2 days\" --hours 48"
    echo "  dm-consequence.sh check"
    echo "  dm-consequence.sh resolve abc123 \"Party escaped the city\""
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-consequence.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    add)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-consequence.sh add <description> <trigger> [--hours N]"
            exit 1
        fi
        $WG consequence-add "$@"
        ;;

    check)
        $WG consequence-check
        ;;

    resolve)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-consequence.sh resolve <id> [resolution]"
            exit 1
        fi
        $WG consequence-resolve "$@"
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, check, resolve"
        dispatch_middleware_help "dm-consequence.sh"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-consequence.sh" "$ACTION" "$@"
exit $CORE_RC
