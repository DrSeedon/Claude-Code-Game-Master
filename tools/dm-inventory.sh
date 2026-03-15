#!/bin/bash
# Inventory management — stackable items, unique items, weight, transfers
source "$(dirname "$0")/common.sh"

$PYTHON_CMD "$LIB_DIR/inventory_manager.py" "$@"
CORE_RC=$?
dispatch_middleware_post "dm-inventory.sh" "$@"
exit $CORE_RC
