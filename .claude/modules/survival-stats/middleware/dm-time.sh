#!/bin/bash
# survival-stats middleware for dm-time.sh
# Handles: --elapsed, --precise-time, --sleeping

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for arg in "$@"; do
    case "$arg" in
        --elapsed|--precise-time|--sleeping)
            exec bash "$MODULE_DIR/tools/dm-survival.sh" time "$@"
            ;;
    esac
done

exit 1
