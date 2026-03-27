#!/bin/bash
# Hook 2/3: Campaign state + module status (stdout → context)
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/dm-hook-common.sh"
[ -z "$CAMPAIGN_DIR" ] && exit 0

echo "=== CAMPAIGN STATE ==="
bash "$PROJECT_ROOT/tools/dm-session.sh" context 2>/dev/null
echo ""
bash "$PROJECT_ROOT/.claude/additional/infrastructure/tools/dm-module-status.sh" 2>/dev/null
echo ""
echo "=== END CAMPAIGN STATE ==="
