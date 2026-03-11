#!/bin/bash
# Enhanced dice middleware — intercepts dm-roll.sh, adds --label/--dc/--ac support
# If no enhanced flags present, passes through to CORE dice.py

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$1" = "--help" ]; then
    echo "  dm-roll.sh <dice> [--label <text>] [--dc <N>] [--ac <N>]"
    echo ""
    echo "  Examples:"
    echo "    dm-roll.sh 1d20+5 --label 'Perception (Рекс)' --dc 15"
    echo "    dm-roll.sh 1d20+7 --label 'Attack (Хантер)' --ac 14"
    echo "    dm-roll.sh 2d20kh1+5 --label 'Stealth (advantage)' --dc 12"
    echo "    dm-roll.sh 3d6+2       # plain roll, no label"
    exit 1
fi

_dir="$MODULE_DIR"
while [ ! -d "$_dir/.git" ] && [ "$_dir" != "/" ]; do _dir="$(dirname "$_dir")"; done
PROJECT_ROOT="$_dir"
PYTHON_CMD="uv run python"

$PYTHON_CMD "$MODULE_DIR/lib/enhanced_dice.py" "$@"
exit 0
