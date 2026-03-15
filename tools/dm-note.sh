#!/bin/bash
# dm-note.sh - Record immutable world facts (wrapper for note_manager.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-note.sh <category> <fact>"
    echo "       dm-note.sh categories"
    echo ""
    echo "Categories: session_events, player_choices, npc_relations, world_lore, lore, rules"
    echo "  (Plot/quest data belongs in dm-plot.sh, not notes)"
    echo ""
    echo "Example: dm-note.sh \"volcano\" \"The volcano god demands royal blood\""
    exit 1
fi

require_active_campaign

dispatch_middleware "dm-note.sh" "$@" && exit $?

if [ "$1" = "categories" ]; then
    echo "Fact Categories:"
    $PYTHON_CMD -m lib.note_manager categories
    exit $?
elif [ "$#" -eq 2 ]; then
    $PYTHON_CMD -m lib.note_manager add "$1" "$2"
    CORE_RC=$?
    dispatch_middleware_post "dm-note.sh" "$@"
    exit $CORE_RC
else
    echo "Usage: dm-note.sh <category> <fact>"
    exit 1
fi
