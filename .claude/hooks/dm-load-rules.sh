#!/bin/bash
# Hook 1/3: Compile DM rules to /tmp file (NO stdout — too large for context)
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dm-hook-common.sh"
[ -z "$CAMPAIGN_DIR" ] && exit 0

bash "$PROJECT_ROOT/.claude/additional/infrastructure/dm-active-modules-rules.sh" > /tmp/dm-rules.md 2>/dev/null

CAMPAIGN_RULES="$CAMPAIGN_DIR/campaign-rules.md"
[ -f "$CAMPAIGN_RULES" ] && cat "$CAMPAIGN_RULES" >> /tmp/dm-rules.md

cd "$PROJECT_ROOT" || exit 1
uv run python - "$PROJECT_ROOT" "$CAMPAIGN_DIR/campaign-overview.json" >> /tmp/dm-rules.md <<'PY'
import json
import sys
from pathlib import Path
from lib.narrator_style import render_narrator_style

overview = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
style = render_narrator_style(Path(sys.argv[1]), overview.get("narrator_style"))
if style:
    print("\n---\n" + style)
PY
if [ $? -ne 0 ]; then
    echo "Failed to load campaign narrator style." >&2
    exit 1
fi

SIZE=$(wc -c < /tmp/dm-rules.md)
echo "DM rules compiled to /tmp/dm-rules.md (${SIZE} bytes). Read this file at session start."
