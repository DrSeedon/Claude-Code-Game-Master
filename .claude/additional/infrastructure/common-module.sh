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
    while [ ! -d "$dir/.git" ] && [ "$dir" != "/" ]; do
        dir="$(dirname "$dir")"
    done
    if [ -d "$dir/.git" ]; then
        echo "$dir"
    else
        echo ""
        return 1
    fi
}
