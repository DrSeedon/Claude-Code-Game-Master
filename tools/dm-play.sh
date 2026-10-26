#!/bin/bash
# Online screen table: status, campaign switch, screen restart, pause and resume (driver: backend.screen_driver).

source "$(dirname "$0")/common.sh"

cd "$PROJECT_ROOT" && $PYTHON_CMD -m lib.screen.online "$@"
