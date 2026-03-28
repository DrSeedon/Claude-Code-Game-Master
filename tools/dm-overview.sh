#!/bin/bash
# dm-overview.sh - World state overview (thin wrapper for world_graph.py)

source "$(dirname "$0")/common.sh"

require_active_campaign

echo "WORLD STATE OVERVIEW"
echo "===================="

$PYTHON_CMD "$LIB_DIR/world_graph.py" stats
RESULT=$?

echo ""
echo "Use dm-search.sh to search for specific content"
exit $RESULT
