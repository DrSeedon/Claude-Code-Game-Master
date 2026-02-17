#!/usr/bin/env bash
#
# dm-module.sh - Module Management
# List, scan, and manage DM System modules
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Run module loader
uv run python lib/module_loader.py "$@"
