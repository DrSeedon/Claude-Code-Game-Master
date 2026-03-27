#!/bin/bash
# dm-note.sh - Record world facts (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-note.sh <category> <fact>"
    echo "       dm-note.sh list [--category X]"
    echo "       dm-note.sh search <query>"
    echo ""
    echo "Categories: session_events, player_choices, npc_relations, world_lore, lore, rules"
    echo "  (Plot/quest data belongs in dm-plot.sh, not notes)"
    echo ""
    echo "Example: dm-note.sh \"volcano\" \"The volcano god demands royal blood\""
    exit 1
fi

require_active_campaign

dispatch_middleware "dm-note.sh" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$1" in
    list)
        shift
        $WG fact-list "$@"
        ;;
    search)
        shift
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-note.sh search <query>"
            exit 1
        fi
        $WG fact-search "$1"
        ;;
    categories)
        echo "Fact Categories: session_events, player_choices, npc_relations, world_lore, lore, rules"
        ;;
    *)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-note.sh <category> <fact>"
            exit 1
        fi
        $WG fact-add "$1" "$2"
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-note.sh" "$@"
exit $CORE_RC
