#!/usr/bin/env bash
#
# dm-combat.sh - Firearms Combat Resolver
# Automated combat resolution for modern/STALKER campaigns
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Find project root
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

uv run python "$MODULE_ROOT/lib/firearms_resolver.py" "$@"
