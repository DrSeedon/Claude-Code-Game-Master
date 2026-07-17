#!/bin/bash
# Get or set the active campaign's player-agency mode.

source "$(dirname "$0")/common.sh"
require_active_campaign

$PYTHON_CMD "$LIB_DIR/campaign_mode.py" "$@"
