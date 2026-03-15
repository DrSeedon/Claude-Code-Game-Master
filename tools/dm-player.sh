#!/bin/bash
# Player Character management for D&D campaign
# Thin CLI wrapper - logic in lib/player_manager.py

# Source common utilities
source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION=$1
shift

dispatch_middleware "dm-player.sh" "$ACTION" "$@" && exit $?

case "$ACTION" in
    "show")
        if [ -z "$1" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" show
        else
            $PYTHON_CMD "$LIB_DIR/player_manager.py" show "$1"
        fi
        ;;

    "list")
        $PYTHON_CMD "$LIB_DIR/player_manager.py" list
        ;;

    "save-json")
        # Save character from JSON data
        CHARACTER_JSON="$*"
        if [ -z "$CHARACTER_JSON" ]; then
            echo "Usage: dm-player.sh save-json '<json_data>'"
            echo "Example: dm-player.sh save-json '{\"name\":\"Thorin\",\"race\":\"Dwarf\",\"class\":\"Fighter\",\"level\":1}'"
            exit 1
        fi
        $PYTHON_CMD "$PROJECT_ROOT/features/character-creation/save_character.py" "$CHARACTER_JSON"
        ;;

    "set")
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh set <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" set "$1"
        ;;

    "xp")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: dm-player.sh xp <character_name> <+amount>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" xp "$1" "$2"
        ;;

    "level-check")
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh level-check <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" level-check "$1"
        ;;

    "hp")
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh hp [character_name] <+/-amount>"
            exit 1
        fi
        if [[ "$1" =~ ^(heal|damage)$ ]] && [ -n "$2" ]; then
            if [ "$1" = "heal" ]; then
                $PYTHON_CMD "$LIB_DIR/player_manager.py" hp "_auto" "+$2"
            else
                $PYTHON_CMD "$LIB_DIR/player_manager.py" hp "_auto" "-$2"
            fi
        elif [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" hp "_auto" "$1"
        elif [ -z "$2" ]; then
            echo "Usage: dm-player.sh hp [character_name] <+/-amount>"
            exit 1
        else
            $PYTHON_CMD "$LIB_DIR/player_manager.py" hp "$1" "$2"
        fi
        ;;

    "get")
        if [ -z "$1" ]; then
            echo "Usage: dm-player.sh get <character_name>"
            exit 1
        fi
        $PYTHON_CMD "$LIB_DIR/player_manager.py" get "$1"
        ;;

    "gold")
        # Amount is in base currency units (copper pieces for D&D).
        # Examples: gold <name> +250 (adds 250 cp = 2g 5s)
        #           gold <name> +"2gp 5sp" (multi-denomination string)
        if [ -z "$1" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" gold "_auto"
        elif [[ "$1" =~ ^[+-]?[0-9]+$ ]] && [ -z "$2" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" gold "_auto" "$1"
        elif [ -z "$2" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" gold "$1"
        else
            $PYTHON_CMD "$LIB_DIR/player_manager.py" gold "$1" "$2"
        fi
        ;;

    "condition")
        if [ -z "$1" ] || [ -z "$2" ]; then
            echo "Usage: dm-player.sh condition <character_name> <action> [condition]"
            echo ""
            echo "Actions:"
            echo "  add <condition>    - Add condition to character"
            echo "  remove <condition> - Remove condition from character"
            echo "  list               - Show current conditions"
            echo ""
            echo "Example: dm-player.sh condition Tandy add poisoned"
            echo "Example: dm-player.sh condition Tandy remove poisoned"
            echo "Example: dm-player.sh condition Tandy list"
            exit 1
        fi
        if [ "$2" = "list" ]; then
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$1" "$2"
        else
            if [ -z "$3" ]; then
                echo "Error: Condition name required for $2"
                exit 1
            fi
            $PYTHON_CMD "$LIB_DIR/player_manager.py" condition "$1" "$2" "$3"
        fi
        ;;

    *)
        echo "D&D Player Character Manager"
        echo "Usage: dm-player.sh <action> [args]"
        echo ""
        echo "Actions:"
        echo "  show [name]                  - Show player(s) summary"
        echo "  get <name>                   - Get full character JSON"
        echo "  list                         - List all player IDs"
        echo "  set <name>                   - Set character as current active PC"
        echo "  xp <name> +<amount>          - Award XP to character"
        echo "  hp <name> <+/-amount>        - Modify character HP"
        echo "  gold <name> [+/-amount]      - Modify or show character money (base units = copper)"
        echo "  condition <name> <action>    - Manage conditions (add/remove/list)"
        echo "  level-check <name>           - Check XP and level status"
        echo "  save-json '<json>'           - Save complete character from JSON"
        echo ""
        echo "Note: Character is stored in the active campaign's character.json"
        dispatch_middleware_help "dm-player.sh"
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-player.sh" "$ACTION" "$@"
exit $CORE_RC
