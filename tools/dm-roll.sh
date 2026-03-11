#!/bin/bash
# Dice rolling for D&D campaign
# Thin CLI wrapper - logic in lib/dice.py

source "$(dirname "$0")/common.sh"

dispatch_middleware "dm-roll.sh" "$@" && exit $?

$PYTHON_CMD "$LIB_DIR/dice.py" "$@"
