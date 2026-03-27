#!/bin/bash
# Player Character management — delegates to world_graph.py; falls back to player_manager.py for unsupported actions

source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION=$1
shift

dispatch_middleware "dm-player.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    show)
        $WG player-show
        ;;

    list)
        $PYTHON_CMD "$LIB_DIR/player_manager.py" list
        ;;

    get)
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh get <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" get "$1"
        ;;

    save-json)
        CHARACTER_JSON="$*"
        if [ -z "$CHARACTER_JSON" ]; then
            echo "Usage: dm-player.sh save-json '<json_data>'"
            exit 1
        fi
        $PYTHON_CMD "$PROJECT_ROOT/features/character-creation/save_character.py" "$CHARACTER_JSON"
        ;;

    set)
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh set <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" set "$1"
        ;;

    xp)
        DELTA=""
        if [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            DELTA="$1"
        elif [ -n "$2" ]; then
            DELTA="$2"
        else
            echo "Usage: dm-player.sh xp [character_name] <+amount>"
            exit 1
        fi
        $WG player-xp "$DELTA"
        ;;

    hp)
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh hp [character_name] <+/-amount>"
            exit 1
        fi
        if [[ "$1" =~ ^(heal|damage)$ ]] && [ -n "$2" ]; then
            [ "$1" = "heal" ] && $WG player-hp "+$2" || $WG player-hp "-$2"
        elif [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            $WG player-hp "$1"
        elif [ -n "$2" ]; then
            $WG player-hp "$2"
        else
            echo "Usage: dm-player.sh hp [character_name] <+/-amount>"
            exit 1
        fi
        ;;

    hp-max)
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh hp-max [character_name] <+/-amount>"
            exit 1
        fi
        if [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            DELTA="$1"
        elif [ -n "$2" ]; then
            DELTA="$2"
        else
            echo "Usage: dm-player.sh hp-max [character_name] <+/-amount>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" hp-max "_auto" "$DELTA"
        ;;

    gold)
        if [ -z "$1" ]; then
            $WG player-show
        elif [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            $WG player-gold "$1"
        elif [ -z "$2" ]; then
            $WG player-show
        else
            $WG player-gold "$2"
        fi
        ;;

    condition)
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: dm-player.sh condition <character_name> <action> [condition]"
            echo ""
            echo "Actions:"
            echo "  add <condition>    - Add condition to character"
            echo "  remove <condition> - Remove condition from character"
            echo "  list               - Show current conditions"
            exit 1
        fi
        CHAR="$1"
        COND_ACTION="$2"
        COND_NAME="$3"
        if [ "$COND_ACTION" = "list" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$CHAR" list
        else
            if [ -z "$COND_NAME" ]; then
                echo "Error: Condition name required for $COND_ACTION"
                exit 1
            fi
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$CHAR" "$COND_ACTION" "$COND_NAME"
        fi
        ;;

    level-check)
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh level-check <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" level-check "$1"
        ;;

    custom-stat)
        dispatch_middleware "dm-player.sh" "custom-stat" "$@"
        MRET=$?
        if [ $MRET -ne 0 ]; then
            echo "Error: custom-stat requires custom-stats module"
            exit 1
        fi
        exit $MRET
        ;;

    *)
        echo "D&D Player Character Manager"
        echo "Usage: dm-player.sh <action> [args]"
        echo ""
        echo "Actions:"
        echo "  show                         - Show player character sheet"
        echo "  get <name>                   - Get full character JSON"
        echo "  list                         - List all player IDs"
        echo "  set <name>                   - Set character as current active PC"
        echo "  xp [name] <+amount>          - Award XP to character"
        echo "  hp [name] <+/-amount>        - Modify character HP"
        echo "  hp-max [name] <+/-amount>    - Modify max HP"
        echo "  gold [name] [+/-amount]      - Modify or show character money"
        echo "  condition <name> <action>    - Manage conditions (add/remove/list)"
        echo "  level-check <name>           - Check XP and level status"
        echo "  save-json '<json>'           - Save complete character from JSON"
        dispatch_middleware_help "dm-player.sh"
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-player.sh" "$ACTION" "$@"
exit $CORE_RC
