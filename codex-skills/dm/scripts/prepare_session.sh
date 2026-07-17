#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ACTIVE_FILE="$PROJECT_ROOT/world-state/active-campaign.txt"

cd "$PROJECT_ROOT"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/dm-uv-cache}"

if [[ ! -s "$ACTIVE_FILE" ]]; then
  echo "No active campaign. Run the /dm campaign selection first." >&2
  exit 2
fi

ACTIVE="$(<"$ACTIVE_FILE")"
if [[ ! -d "$PROJECT_ROOT/world-state/campaigns/$ACTIVE" ]]; then
  echo "Active campaign directory does not exist: $ACTIVE" >&2
  exit 2
fi

PROMPT='{"prompt":"/dm-continue"}'
printf '%s' "$PROMPT" | bash .claude/hooks/dm-load-rules.sh

echo
echo "=== SESSION REGISTRATION ==="
bash tools/dm-session.sh start
echo

printf '%s' "$PROMPT" | bash .claude/hooks/dm-load-campaign.sh
echo
printf '%s' "$PROMPT" | bash .claude/hooks/dm-load-session.sh

if [[ ! -s /tmp/dm-rules.md ]]; then
  echo "DM rules were not compiled." >&2
  exit 3
fi

echo
echo "Read /tmp/dm-rules.md before narrating."
