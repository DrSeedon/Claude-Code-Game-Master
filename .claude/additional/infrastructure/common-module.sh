#!/bin/bash
# common-module.sh - Shared helpers for module scripts
# Source this file from any module script:
#   source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../../../../infrastructure/common-module.sh"
# Or use find_project_root directly after sourcing.

# Clear inherited VIRTUAL_ENV to prevent uv warnings
unset VIRTUAL_ENV

find_project_root() {
    local start="${1:-$(pwd)}"
    local dir="$start"
    # `.git` is a DIRECTORY in a normal clone but a FILE in a git worktree —
    # test for existence (-e), not -d, so this resolves the worktree root too.
    while [ ! -e "$dir/.git" ] && [ "$dir" != "/" ]; do
        dir="$(dirname "$dir")"
    done
    if [ -e "$dir/.git" ]; then
        echo "$dir"
    else
        echo ""
        return 1
    fi
}
