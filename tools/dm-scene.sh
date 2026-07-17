#!/bin/bash
# dm-scene.sh - Apply a complete narrative scene transition in one command.

source "$(dirname "$0")/common.sh"
require_active_campaign

exec $PYTHON_CMD -m lib.scene_manager "$@"
