#!/usr/bin/env bash
# Module status for session start: custom-stats via WorldGraph

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../infrastructure/common-module.sh"
PROJECT_ROOT="$(find_project_root "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"

cd "$PROJECT_ROOT"
uv run python lib/world_graph.py custom-stat-list 2>/dev/null
uv run python lib/world_graph.py timed-effect-list 2>/dev/null
