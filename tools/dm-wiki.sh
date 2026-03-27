#!/bin/bash
# dm-wiki.sh — Structured wiki knowledge base for campaign entities
# Usage:
#   bash tools/dm-wiki.sh add "id" --name "Name" --type potion --desc "..." [--dc N] [--skill S] [--ingredient "id:qty"] [--effect "..."] [--ref "id"] [--tag "t"]
#   bash tools/dm-wiki.sh show "id"
#   bash tools/dm-wiki.sh list [--type potion] [--tag alchemy]
#   bash tools/dm-wiki.sh search "query"
#   bash tools/dm-wiki.sh recipe "id"
#   bash tools/dm-wiki.sh remove "id"

source "$(dirname "$0")/common.sh"
require_active_campaign

$PYTHON_CMD "$LIB_DIR/wiki_manager.py" "$@"
