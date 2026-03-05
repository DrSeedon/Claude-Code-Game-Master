#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Find project root
_dir="$SCRIPT_DIR"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"
cd "$PROJECT_ROOT"
uv run python "$MODULE_ROOT/lib/inventory_manager.py" "$@"
