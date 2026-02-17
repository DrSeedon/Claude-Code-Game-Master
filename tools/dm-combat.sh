#!/usr/bin/env bash
#
# dm-combat.sh - Firearms Combat Resolver
# Automated combat resolution for modern/STALKER campaigns
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Run combat resolver
uv run python lib/combat_resolver.py "$@"
