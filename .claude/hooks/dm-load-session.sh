#!/bin/bash
# Hook 3/3: Quests, consequences, last session, handoff (stdout → context)
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dm-hook-common.sh"
[ -z "$CAMPAIGN_DIR" ] && exit 0

echo "=== SESSION CONTEXT ==="
echo ""

echo "--- CONSEQUENCES ---"
bash "$PROJECT_ROOT/tools/dm-consequence.sh" check 2>/dev/null
echo ""

echo "--- ACTIVE QUESTS ---"
bash "$PROJECT_ROOT/tools/dm-plot.sh" list --status active 2>/dev/null
echo ""

echo "--- LAST SESSION ---"
SESSION_LOG="$CAMPAIGN_DIR/session-log.md"
if [ -f "$SESSION_LOG" ]; then
    LAST_ENDED=$(grep -n "^### Session Ended:" "$SESSION_LOG" | tail -1 | cut -d: -f1)
    if [ -n "$LAST_ENDED" ]; then
        sed -n "${LAST_ENDED},\$p" "$SESSION_LOG" | head -20
    else
        tail -20 "$SESSION_LOG"
    fi
fi
echo ""

HANDOFF="$CAMPAIGN_DIR/session-handoff.md"
if [ -f "$HANDOFF" ]; then
    echo "--- SESSION HANDOFF ---"
    cat "$HANDOFF"
    echo ""
fi

echo "=== END SESSION CONTEXT ==="
