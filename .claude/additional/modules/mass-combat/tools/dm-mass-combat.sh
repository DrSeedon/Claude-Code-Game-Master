#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"
uv run python "$MODULE_ROOT/lib/mass_combat_engine.py" "$@"
