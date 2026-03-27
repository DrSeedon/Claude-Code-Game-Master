#!/bin/bash
# Hook 1/3: Compile DM rules to /tmp file (NO stdout — too large for context)
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dm-hook-common.sh"
[ -z "$CAMPAIGN_DIR" ] && exit 0

bash "$PROJECT_ROOT/.claude/additional/infrastructure/dm-active-modules-rules.sh" > /tmp/dm-rules.md 2>/dev/null

CAMPAIGN_RULES="$CAMPAIGN_DIR/campaign-rules.md"
[ -f "$CAMPAIGN_RULES" ] && cat "$CAMPAIGN_RULES" >> /tmp/dm-rules.md

NARRATOR_STYLE=$(python3 -c "import json; d=json.load(open('$CAMPAIGN_DIR/campaign-overview.json')); print(d.get('narrator_style',''))" 2>/dev/null)
if [ -n "$NARRATOR_STYLE" ]; then
    STYLE_FILE="$PROJECT_ROOT/.claude/additional/narrator-styles/$NARRATOR_STYLE.md"
    [ -f "$STYLE_FILE" ] && cat "$STYLE_FILE" >> /tmp/dm-rules.md
fi

SIZE=$(wc -c < /tmp/dm-rules.md)
echo "DM rules compiled to /tmp/dm-rules.md (${SIZE} bytes). Read this file at session start."
