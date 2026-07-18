#!/usr/bin/env bash
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
exec uv run uvicorn backend.server:app --host 127.0.0.1 --port 18083
