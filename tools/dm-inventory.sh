#!/bin/bash
# Inventory management — delegates to world_graph.py; falls back to inventory_manager.py for unsupported actions
source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-inventory.sh" "$ACTION" "$@" && exit $?

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

case "$ACTION" in
    show)
        OWNER="${1:-_auto}"
        $WG inventory-show "$OWNER"
        ;;

    loot)
        # loot <char> --items "name:qty:weight" [--gold N] [--xp N]
        OWNER="$1"
        shift
        ITEMS=""
        GOLD=""
        XP=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --items) ITEMS="$2"; shift 2 ;;
                --gold)  GOLD="$2";  shift 2 ;;
                --xp)    XP="$2";    shift 2 ;;
                *)       shift ;;
            esac
        done

        if [ -n "$ITEMS" ]; then
            IFS=',' read -ra ITEM_LIST <<< "$ITEMS"
            for ENTRY in "${ITEM_LIST[@]}"; do
                IFS=':' read -ra PARTS <<< "$ENTRY"
                INAME="${PARTS[0]}"
                IQTY="${PARTS[1]:-1}"
                IWT="${PARTS[2]:-0.5}"
                [ -n "$INAME" ] && $WG inventory-add "$OWNER" "$INAME" --qty "$IQTY" --weight "$IWT"
            done
        fi
        [ -n "$GOLD" ] && $WG player-gold "$GOLD"
        [ -n "$XP"   ] && $WG player-xp   "$XP"
        ;;

    remove)
        OWNER="$1"
        ITEM="$2"
        shift 2
        QTY=1
        while [ $# -gt 0 ]; do
            case "$1" in
                --qty) QTY="$2"; shift 2 ;;
                *) shift ;;
            esac
        done
        $WG inventory-remove "$OWNER" "$ITEM" --qty "$QTY"
        ;;

    update)
        # update <char> [--add "item" qty weight] [--gold N] [--hp N]
        OWNER="$1"
        shift
        while [ $# -gt 0 ]; do
            case "$1" in
                --add)
                    INAME="$2"; IQTY="${3:-1}"; IWT="${4:-0.5}"
                    $WG inventory-add "$OWNER" "$INAME" --qty "$IQTY" --weight "$IWT"
                    shift 4
                    ;;
                --gold)
                    $WG player-gold "$2"
                    shift 2
                    ;;
                --hp)
                    $WG player-hp "$2"
                    shift 2
                    ;;
                *)
                    shift
                    ;;
            esac
        done
        ;;

    transfer)
        # transfer <target> --from <source> --item "name" [N]
        TARGET="$1"
        shift
        SOURCE=""
        ITEM=""
        QTY=1
        while [ $# -gt 0 ]; do
            case "$1" in
                --from) SOURCE="$2"; shift 2 ;;
                --item) ITEM="$2";   shift 2 ;;
                --qty)  QTY="$2";    shift 2 ;;
                [0-9]*) QTY="$1";   shift ;;
                *)       shift ;;
            esac
        done
        $WG inventory-transfer "$SOURCE" "$TARGET" "$ITEM" --qty "$QTY"
        ;;

    party)
        $WG npc-list
        ;;

    status)
        $WG player-show
        ;;

    weigh)
        OWNER="${1:-_auto}"
        $WG inventory-show "$OWNER"
        ;;

    craft|use)
        $PYTHON_CMD "$LIB_DIR/inventory_manager.py" "$ACTION" "$@"
        ;;

    *)
        $PYTHON_CMD "$LIB_DIR/inventory_manager.py" "$ACTION" "$@"
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-inventory.sh" "$ACTION" "$@"
exit $CORE_RC
