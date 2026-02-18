#!/bin/bash
cd "$(dirname "$0")"
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --gui "$@"
