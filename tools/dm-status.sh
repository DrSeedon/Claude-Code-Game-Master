#!/bin/bash
# Compact inventory status for session start
source "$(dirname "$0")/common.sh"

$PYTHON_CMD "$LIB_DIR/inventory_manager.py" status
