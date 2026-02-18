#!/bin/bash
# Core wrapper for inventory management
# Delegates to inventory-system module via middleware dispatch

source "$(dirname "$0")/common.sh"
require_active_campaign

dispatch_middleware "dm-inventory.sh" "$@" || {
    echo "[ERROR] inventory-system module not found"
    echo "Install: .claude/modules/inventory-system/"
    exit 1
}
