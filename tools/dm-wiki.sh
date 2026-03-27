#!/bin/bash
# dm-wiki.sh - Structured wiki knowledge base (delegates to world_graph.py)

source "$(dirname "$0")/common.sh"

if [ "$#" -lt 1 ]; then
    echo "Usage: dm-wiki.sh <action> [args]"
    echo ""
    echo "Actions:"
    echo "  add <id> --name N --type T [--stat k:v] [--ingredient id:qty] [--dc N] [--skill S]"
    echo "  show <id>          - Show wiki entity"
    echo "  list [--type T]    - List wiki entities"
    echo "  search <query>     - Search wiki"
    echo "  remove <id>        - Remove entity"
    echo "  recipe <id>        - Show recipe for entity"
    echo ""
    echo "Examples:"
    echo "  dm-wiki.sh add \"health-potion\" --name \"Health Potion\" --type item --stat \"heal:2d4+2\""
    echo "  dm-wiki.sh show \"health-potion\""
    echo "  dm-wiki.sh list --type item"
    exit 1
fi

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-wiki.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    add)
        $WG wiki-add "$@"
        ;;

    show|recipe)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-wiki.sh $ACTION <id>"
            exit 1
        fi
        $WG wiki-show "$1"
        ;;

    list)
        $WG wiki-list "$@"
        ;;

    search)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-wiki.sh search <query>"
            exit 1
        fi
        $WG wiki-search "$1"
        ;;

    remove)
        if [ "$#" -lt 1 ]; then
            echo "Usage: dm-wiki.sh remove <id>"
            exit 1
        fi
        $WG wiki-remove "$1"
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Valid actions: add, show, list, search, remove, recipe"
        dispatch_middleware_help "dm-wiki.sh"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-wiki.sh" "$ACTION" "$@"
exit $CORE_RC
