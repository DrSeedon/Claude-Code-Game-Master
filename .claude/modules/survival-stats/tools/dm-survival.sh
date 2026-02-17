#!/usr/bin/env bash
#
# dm-survival.sh - Survival Stats Module
# Apply time effects to custom stats, check stat consequences
#
# Usage:
#   bash .claude/modules/survival-stats/tools/dm-survival.sh tick --elapsed 2
#   bash .claude/modules/survival-stats/tools/dm-survival.sh tick --elapsed 8 --sleeping
#   bash .claude/modules/survival-stats/tools/dm-survival.sh status
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

cd "$PROJECT_ROOT"

uv run python .claude/modules/survival-stats/lib/survival_engine.py "$@"
