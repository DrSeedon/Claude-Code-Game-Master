#!/usr/bin/env bash
# Migrate one campaign's legacy flat JSON files into world.json.

source "$(dirname "$0")/common.sh"

if [ -n "$1" ] && [[ "$1" != --* ]]; then
    CAMPAIGN="$1"
    shift
else
    CAMPAIGN="$(_scoped_campaign_name)"
fi
if [ -z "$CAMPAIGN" ]; then
    echo "Usage: dm-migrate-worldgraph.sh [campaign] [--dry-run|--remove-legacy]"
    exit 1
fi

CAMPAIGN_DIR=$($PYTHON_CMD "$LIB_DIR/campaign_manager.py" path "$CAMPAIGN") || {
    echo "Campaign not found: $CAMPAIGN"
    exit 1
}

$PYTHON_CMD "$LIB_DIR/legacy_migration.py" "$CAMPAIGN_DIR" "$@"
