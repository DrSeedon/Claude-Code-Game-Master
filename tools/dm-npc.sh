#!/bin/bash
# dm-npc.sh - NPC management (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-npc.sh <action> [name] [args]"
    echo ""
    echo "=== NPC Management ==="
    echo "  create <name> <description> <attitude>  Create new NPC"
    echo "  update <name> <event>                   Add event to NPC history"
    echo "  status <name>                           Show NPC details"
    echo "  show <name>                             Show NPC details"
    echo "  list [--attitude X] [--location Y]      List all NPCs"
    echo ""
    echo "=== Party Members ==="
    echo "  promote <name>                          Make NPC a party member"
    echo "  demote <name>                           Remove party member status"
    echo "  party                                   List all party members"
    echo ""
    echo "=== Other ==="
    echo "  event <name> <text>                     Add event to NPC"
    echo "  attitude <name> <attitude>              Update NPC attitude"
    echo "  hp <name> <+/-amount>                   Damage/heal party member"
    echo "  locate <name> <location>                Set NPC current location"
    echo ""
    echo "Examples:"
    echo "  dm-npc.sh create \"Carl\" \"A dungeon crawler\" \"friendly\""
    echo "  dm-npc.sh promote \"Carl\""
    echo "  dm-npc.sh hp \"Carl\" -4"
    echo "  dm-npc.sh party"
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-npc.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    create)
        if [ "$#" -lt 3 ]; then
            echo "Usage: dm-npc.sh create <name> <description> <attitude>"
            exit 1
        fi
        $WG npc-create "$1" "$2" --attitude "$3"
        ;;

    list)
        $WG npc-list
        ;;

    party)
        $WG npc-list
        ;;

    show|status)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-npc.sh $ACTION <name>"
            exit 1
        fi
        STATUS_OUTPUT=$($WG npc-show "$1")
        STATUS_CODE=$?
        echo "$STATUS_OUTPUT"

        CAMPAIGN_DIR=$(bash "$TOOLS_DIR/dm-campaign.sh" path 2>/dev/null)
        RAG_OUTPUT=""
        RAG_CODE=0
        if [ -d "$CAMPAIGN_DIR/vectors" ]; then
            echo ""
            echo "Source Material Context"
            echo "======================="
            RAG_OUTPUT=$($PYTHON_CMD "$LIB_DIR/entity_enhancer.py" search "$1 personality dialogue background" -n 4 --excerpt-chars 250)
            RAG_CODE=$?
            echo "$RAG_OUTPUT"
        fi

        STATUS_CHARS=${#STATUS_OUTPUT}
        RAG_CHARS=${#RAG_OUTPUT}
        STATUS_TOKENS=$(estimate_tokens_from_chars "$STATUS_CHARS")
        RAG_TOKENS=$(estimate_tokens_from_chars "$RAG_CHARS")
        log_token_usage "dm-npc-status" "name_chars=${#1}" "status_chars=$STATUS_CHARS" "status_tokens_est=$STATUS_TOKENS" "rag_chars=$RAG_CHARS" "rag_tokens_est=$RAG_TOKENS"

        if [ $STATUS_CODE -ne 0 ]; then exit $STATUS_CODE; fi
        if [ $RAG_CODE -ne 0 ]; then exit $RAG_CODE; fi
        ;;

    update|event)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-npc.sh $ACTION <name> <event>"
            exit 1
        fi
        $WG npc-event "$1" "$2"
        ;;

    promote)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-npc.sh promote <name>"
            exit 1
        fi
        $WG npc-promote "$1"
        ;;

    demote)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-npc.sh demote <name>"
            exit 1
        fi
        NPC_ID=$($PYTHON_CMD -c "
import sys; sys.path.insert(0,'$LIB_DIR')
from world_graph import WorldGraph
g = WorldGraph()
nid = g._resolve_id('$1', 'npc')
print(nid or '')
" 2>/dev/null)
        if [ -z "$NPC_ID" ]; then echo "Error: NPC '$1' not found"; exit 1; fi
        $WG update-node "$NPC_ID" --data '{"party_member": false}'
        ;;

    attitude)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-npc.sh attitude <name> <attitude>"
            exit 1
        fi
        NPC_ID=$($PYTHON_CMD -c "
import sys; sys.path.insert(0,'$LIB_DIR')
from world_graph import WorldGraph
g = WorldGraph()
nid = g._resolve_id('$1', 'npc')
print(nid or '')
" 2>/dev/null)
        if [ -z "$NPC_ID" ]; then echo "Error: NPC '$1' not found"; exit 1; fi
        $WG update-node "$NPC_ID" --data "{\"attitude\": \"$2\"}"
        ;;

    hp)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-npc.sh hp <name> <+/-amount>"
            exit 1
        fi
        NPC_ID=$($PYTHON_CMD -c "
import sys; sys.path.insert(0,'$LIB_DIR')
from world_graph import WorldGraph
g = WorldGraph()
nid = g._resolve_id('$1', 'npc')
print(nid or '')
" 2>/dev/null)
        if [ -z "$NPC_ID" ]; then echo "Error: NPC '$1' not found"; exit 1; fi
        $WG update-node "$NPC_ID" --data "{\"hp_delta\": $2}"
        ;;

    locate)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-npc.sh locate <name> <location>"
            exit 1
        fi
        $WG npc-locate "$1" "$2"
        ;;

    *)
        echo "Error: Unknown action '$ACTION'"
        echo "Run 'dm-npc.sh' without arguments to see all available actions"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-npc.sh" "$ACTION" "$@"
exit $CORE_RC
