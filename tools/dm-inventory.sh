#!/bin/bash
# Inventory management — delegates to world_graph.py
source "$(dirname "$0")/common.sh"

require_active_campaign

ACTION="$1"
shift

dispatch_middleware "dm-inventory.sh" "$ACTION" "$@"
MW_RC=$?
[ $MW_RC -ne 64 ] && exit $MW_RC

WG="$PYTHON_CMD $LIB_DIR/world_graph.py"

run_wg() {
    $PYTHON_CMD "$LIB_DIR/world_graph.py" "$@"
}

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

        LOOT_ARGS=(inventory-loot "$OWNER")
        if [ -n "$ITEMS" ]; then
            ITEM_ARGS=()
            IFS=',' read -ra ITEM_LIST <<< "$ITEMS"
            for ENTRY in "${ITEM_LIST[@]}"; do
                IFS=':' read -ra PARTS <<< "$ENTRY"
                INAME="${PARTS[0]}"
                IQTY="${PARTS[1]:-1}"
                IWT="${PARTS[2]:-0.5}"
                [ -n "$INAME" ] && ITEM_ARGS+=("$INAME:$IQTY:$IWT")
            done
            if [ ${#ITEM_ARGS[@]} -gt 0 ]; then
                LOOT_ARGS+=(--items "${ITEM_ARGS[@]}")
            fi
        fi
        [ -n "$GOLD" ] && LOOT_ARGS+=(--gold "$GOLD")
        [ -n "$XP" ] && LOOT_ARGS+=(--xp "$XP")
        run_wg "${LOOT_ARGS[@]}"
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
        UPDATE_ITEMS=()
        UPDATE_GOLD=""
        UPDATE_HP=""
        while [ $# -gt 0 ]; do
            case "$1" in
                --add)
                    INAME="$2"; IQTY="${3:-1}"; IWT="${4:-0.5}"
                    UPDATE_ITEMS+=("$INAME:$IQTY:$IWT")
                    shift 4
                    ;;
                --gold)
                    UPDATE_GOLD="$2"
                    shift 2
                    ;;
                --hp)
                    UPDATE_HP="$2"
                    shift 2
                    ;;
                *)
                    echo "Unknown update option: $1" >&2
                    exit 1
                    ;;
            esac
        done
        if [ ${#UPDATE_ITEMS[@]} -gt 0 ] || [ -n "$UPDATE_GOLD" ]; then
            UPDATE_ARGS=(inventory-loot "$OWNER")
            [ ${#UPDATE_ITEMS[@]} -gt 0 ] && UPDATE_ARGS+=(--items "${UPDATE_ITEMS[@]}")
            [ -n "$UPDATE_GOLD" ] && UPDATE_ARGS+=(--gold "$UPDATE_GOLD")
            run_wg "${UPDATE_ARGS[@]}" || exit $?
        fi
        if [ -n "$UPDATE_HP" ]; then
            run_wg player-hp "$UPDATE_HP" || exit $?
        fi
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

    craft)
        # TODO: needs world_graph.py subcommand inventory-craft
        OWNER="${1:-_auto}"
        shift
        $WG inventory-craft "$OWNER" "$@"
        ;;

    use)
        # TODO: needs world_graph.py subcommand inventory-use
        OWNER="${1:-_auto}"
        ITEM="$2"
        $WG inventory-use "$OWNER" "$ITEM"
        ;;

    *)
        echo "Unknown action: $ACTION"
        echo "Usage: dm-inventory.sh <show|loot|remove|update|transfer|party|status|weigh|craft|use>"
        exit 1
        ;;
esac

CORE_RC=$?
dispatch_middleware_post "dm-inventory.sh" "$ACTION" "$@"
exit $CORE_RC
