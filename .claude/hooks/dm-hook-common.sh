#!/bin/bash
# Shared preamble for DM context hooks.
# Source this, then check: [ -z "$CAMPAIGN_DIR" ] && exit 0

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0
MSG=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt','') or d.get('message',''))" 2>/dev/null || true)

case "$MSG" in
  /dm-continue*|/dm\ *|/dm|*"MANDATORY STARTUP CHECKLIST"*|*"dm-continue"*)
    ;;
  *)
    exit 0
    ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/additional/infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"
[ -z "$PROJECT_ROOT" ] && exit 0

ACTIVE=$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || echo "")
[ -z "$ACTIVE" ] && exit 0

CAMPAIGN_DIR="$PROJECT_ROOT/world-state/campaigns/$ACTIVE"
[ -d "$CAMPAIGN_DIR" ] || exit 0
