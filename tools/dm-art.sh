#!/bin/bash
# Act art through the MultiCode hub: asks dnd-play-art.service for one picture and prints its PNG path
# (client: backend.screen_art request; then: bash tools/dm-screen.sh act --image <path> --title ...).
# The service itself runs from a root-owned copy of backend/screen_art.py, never from this repository.

source "$(dirname "$0")/common.sh"

cd "$PROJECT_ROOT" && $PYTHON_CMD -m backend.screen_art request "$@"
