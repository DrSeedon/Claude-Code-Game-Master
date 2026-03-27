#!/bin/bash
# dm-time.sh - CORE game clock management
# Usage:
#   dm-time.sh <time_of_day> <date> --elapsed N [--sleeping]
#   dm-time.sh "_" <date> --to HH:MM
#   dm-time.sh <time_of_day> <date>   (legacy: just set strings)

source "$(dirname "$0")/common.sh"

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: dm-time.sh <time_of_day> <date> [--elapsed N] [--to HH:MM] [--sleeping]"
    exit 1
fi

require_active_campaign

TIME_OF_DAY="$1"
DATE="$2"
shift 2

ELAPSED=""
TO_TIME=""
SLEEPING=""

while [ $# -gt 0 ]; do
    case "$1" in
        --elapsed) ELAPSED="$2"; shift 2 ;;
        --to)      TO_TIME="$2"; shift 2 ;;
        --sleeping) SLEEPING="--sleeping"; shift ;;
        *) shift ;;
    esac
done

if [ -n "$TO_TIME" ]; then
    # Set exact time — CORE calculates elapsed
    OUTPUT=$($PYTHON_CMD -m lib.time_manager set-time --to "$TO_TIME" 2>&1)
    CORE_RC=$?
    echo "$OUTPUT" | grep -v "^ELAPSED_HOURS=" | grep -v "^SLEEPING="
    ELAPSED_VAL=$(echo "$OUTPUT" | grep "^ELAPSED_HOURS=" | cut -d= -f2)
    SLEEPING_VAL=$(echo "$OUTPUT" | grep "^SLEEPING=1")

elif [ -n "$ELAPSED" ]; then
    # Advance by N hours — CORE advances clock
    OUTPUT=$($PYTHON_CMD -m lib.time_manager advance --elapsed "$ELAPSED" $SLEEPING 2>&1)
    CORE_RC=$?
    echo "$OUTPUT" | grep -v "^ELAPSED_HOURS=" | grep -v "^SLEEPING="
    ELAPSED_VAL="$ELAPSED"
    SLEEPING_VAL="$SLEEPING"

else
    # Legacy: just set time strings
    dispatch_middleware "dm-time.sh" "$TIME_OF_DAY" "$DATE" "$TIME_OF_DAY" "$DATE" && exit $?
    $PYTHON_CMD -m lib.time_manager update "$TIME_OF_DAY" "$DATE"
    CORE_RC=$?
    dispatch_middleware_post "dm-time.sh" "$TIME_OF_DAY" "$DATE" "$TIME_OF_DAY" "$DATE"
    exit $CORE_RC
fi

# Post-hook for modules (custom-stats tick, action tracking)
if [ -n "$ELAPSED_VAL" ] && [ "$ELAPSED_VAL" != "0" ] && [ "$ELAPSED_VAL" != "0.000000" ]; then
    POST_ARGS="--elapsed $ELAPSED_VAL"
    [ -n "$SLEEPING_VAL" ] && POST_ARGS="$POST_ARGS --sleeping"
    dispatch_middleware_post "dm-time.sh" "$TIME_OF_DAY" "$DATE" "$TIME_OF_DAY" "$DATE" $POST_ARGS
fi

exit ${CORE_RC:-0}
