#!/usr/bin/env bash
# Compile CORE slots and active module rules into one resolved gameplay profile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-module.sh"
PROJECT_ROOT="$(find_project_root "$SCRIPT_DIR")"

ACTIVE="${DM_ACTIVE_CAMPAIGN:-$(cat "$PROJECT_ROOT/world-state/active-campaign.txt" 2>/dev/null || true)}"
OVERVIEW="$PROJECT_ROOT/world-state/campaigns/$ACTIVE/campaign-overview.json"

MODE="full"
[ "${1:-}" = "--modules-only" ] && MODE="modules"
[ "${1:-}" = "--core-only" ] && MODE="core"

ARGS=("$PROJECT_ROOT")
[ -f "$OVERVIEW" ] && ARGS+=("$OVERVIEW")
ARGS+=("--mode" "$MODE")

cd "$PROJECT_ROOT"
uv run python lib/dm_rules_compiler.py "${ARGS[@]}"
