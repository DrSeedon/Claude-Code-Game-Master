#!/bin/bash
# Unified world graph CLI — single entry point for all entity operations
source "$(dirname "$0")/common.sh"

$PYTHON_CMD "$LIB_DIR/world_graph.py" "$@"
