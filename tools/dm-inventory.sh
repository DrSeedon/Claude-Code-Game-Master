#!/usr/bin/env bash
#
# dm-inventory.sh - Unified Inventory Manager
# Handles all inventory/stats operations in atomic transactions
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Run inventory manager
uv run python lib/inventory_manager.py "$@"
