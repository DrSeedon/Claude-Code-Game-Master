#!/bin/bash
# HTML play screen: act art + theme, live turns, microphone, player actions.

source "$(dirname "$0")/common.sh"
require_active_campaign

cd "$PROJECT_ROOT" && $PYTHON_CMD -m lib.screen.cli "$@"
