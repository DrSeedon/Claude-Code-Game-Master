#!/bin/bash
# dm-plot.sh - Quest/plot management (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-plot.sh <action> [args]"
    echo ""
    echo "=== Plot Management ==="
    echo "  add <name> [--type X] [--desc ...]       Create a new quest"
    echo "  list [--status Y]                        List quests (filter by status)"
    echo "  show <name>                              Show full quest details"
    echo "  complete <name>                          Mark quest as completed"
    echo "  fail <name>                              Mark quest as failed"
    echo "  objective <name> add <text>              Add objective to quest"
    echo "  objective <name> complete <idx>          Mark objective as done"
    echo ""
    echo "Types: main, side, mystery, threat"
    echo "Status: active, completed, failed"
    echo ""
    echo "Examples:"
    echo "  dm-plot.sh add \"Side Quest\" --type side --desc \"Find the artifact\""
    echo "  dm-plot.sh objective \"Main Quest\" add \"Find key\""
    echo "  dm-plot.sh objective \"Main Quest\" complete 0"
    echo "  dm-plot.sh list --status active"
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-plot.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    add)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh add <name> [--type X] [--desc ...]"
            exit 1
        fi
        NAME="$1"
        shift
        TYPE="side"
        DESC=""
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --type)   TYPE="$2"; shift 2 ;;
                --desc|--description) DESC="$2"; shift 2 ;;
                *) shift ;;
            esac
        done
        if [ -n "$DESC" ]; then
            $WG quest-create "$NAME" --type "$TYPE" --desc "$DESC"
        else
            $WG quest-create "$NAME" --type "$TYPE"
        fi
        ;;

    list)
        $WG quest-list "$@"
        ;;

    show)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh show <name>"
            exit 1
        fi
        $WG quest-show "$1"
        ;;

    objective)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-plot.sh objective <quest_name> add <text>"
            echo "       dm-plot.sh objective <quest_name> complete <idx>"
            exit 1
        fi
        QUEST="$1"
        OBJ_ACTION="$2"
        VALUE="$3"
        case "$OBJ_ACTION" in
            add)
                $WG quest-objective "$QUEST" add "$VALUE"
                ;;
            complete)
                $WG quest-objective "$QUEST" complete "$VALUE"
                ;;
            *)
                echo "Error: objective action must be 'add' or 'complete'"
                exit 1
                ;;
        esac
        ;;

    complete)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh complete <name>"
            exit 1
        fi
        $WG quest-complete "$1"
        ;;

    fail)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh fail <name>"
            exit 1
        fi
        $WG quest-fail "$1"
        ;;

    *)
        echo "Error: Unknown action '$ACTION'"
        echo "Run 'dm-plot.sh' without arguments to see all available actions"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-plot.sh" "$ACTION" "$@"
exit $CORE_RC
