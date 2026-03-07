#!/bin/bash
# dm-plot.sh - Manage plot hooks and storylines
# Uses Python modules for validation and data operations

# Source common utilities
source "$(dirname "$0")/common.sh"

# Usage: dm-plot.sh <action> [args]

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-plot.sh <action> [args]"
    echo ""
    echo "=== Plot Management ==="
    echo "  add <name> [options]             Create a new plot"
    echo "  list [--type X] [--status Y]     List plots (filter by type/status)"
    echo "  show <name>                      Show full plot details"
    echo "  search <query>                   Search plots by name, NPCs, locations"
    echo "  update <name> <event>            Add progress event to plot"
    echo "  complete <name> [outcome]        Mark plot as completed"
    echo "  fail <name> [reason]             Mark plot as failed"
    echo "  objective <name> <obj> [action]  Manage objectives (complete/incomplete/add)"
    echo "  threads                          Active story threads (DM dashboard)"
    echo "  counts                           Show plot statistics"
    echo ""
    echo "Types: main, side, mystery, threat"
    echo "Status: active, completed, failed, dormant"
    echo ""
    echo "Examples:"
    echo "  dm-plot.sh add \"Side Quest\" --type side --description \"Find the artifact\""
    echo "  dm-plot.sh add \"Main Quest\" --type main --objectives \"Find key,Open door\""
    echo "  dm-plot.sh objective \"Main Quest\" \"Find key\" complete"
    echo "  dm-plot.sh objective \"Main Quest\" \"New task\" add"
    echo "  dm-plot.sh list --type main --status active"
    echo "  dm-plot.sh update \"Murder Mystery\" \"Found first clue at docks\""
    exit 1
fi

require_active_campaign

ACTION="$1"
shift  # Remove action from arguments

dispatch_middleware "dm-plot.sh" "$ACTION" "$@" && exit $?

# Delegate to Python module based on action
case "$ACTION" in
    add)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh add <name> [--type X] [--description \"...\"] [--npcs \"a,b\"] [--objectives \"x,y\"]"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" add "$@"
        ;;

    objective)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-plot.sh objective <plot_name> <objective_text> [complete|incomplete|add]"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" objective "$@"
        ;;

    list)
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" list "$@"
        ;;

    show)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh show <name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" show "$1"
        ;;

    search)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh search <query>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" search "$1"
        ;;

    update)
        if [ "$#" -lt 2 ]; then
            echo "Usage: dm-plot.sh update <name> <event>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" update "$1" "$2"
        ;;

    complete)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh complete <name> [outcome]"
            exit 1
        fi
        NAME="$1"
        OUTCOME="${2:-}"
        if [ -n "$OUTCOME" ]; then
            $PYTHON_CMD "$LIB_DIR/plot_manager.py" complete "$NAME" "$OUTCOME"
        else
            $PYTHON_CMD "$LIB_DIR/plot_manager.py" complete "$NAME"
        fi
        ;;

    fail)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-plot.sh fail <name> [reason]"
            exit 1
        fi
        NAME="$1"
        REASON="${2:-}"
        if [ -n "$REASON" ]; then
            $PYTHON_CMD "$LIB_DIR/plot_manager.py" fail "$NAME" "$REASON"
        else
            $PYTHON_CMD "$LIB_DIR/plot_manager.py" fail "$NAME"
        fi
        ;;

    counts)
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" counts
        ;;

    threads)
        $PYTHON_CMD "$LIB_DIR/plot_manager.py" threads
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
