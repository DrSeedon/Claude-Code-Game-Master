#!/bin/bash
# Dice rolling with labels, DC/AC checks
source "$(dirname "$0")/common.sh"

$PYTHON_CMD "$LIB_DIR/dice.py" "$@"
CORE_RC=$?
dispatch_middleware_post "dm-roll.sh" "$@"
exit $CORE_RC
