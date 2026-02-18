#!/bin/bash
# quest-system middleware for dm-plot.sh
# Intercepts 'add' action and delegates to quest-system module
# Other actions (view, update) fall back to core dm-plot.sh

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Only handle 'add' action in this module
if [ "$1" = "add" ]; then
    shift  # remove 'add'
    exec bash "$MODULE_DIR/tools/dm-quest.sh" add "$@"
fi

# All other actions should fall back to core tool
# (This is handled by dispatch_middleware in the core tool wrapper)
exit 1
