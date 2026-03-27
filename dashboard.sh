#!/usr/bin/env bash
PORT=8765
SCRIPT="tools/dm-dashboard"
WATCHER_PID_FILE="/tmp/dm-dashboard-watcher.pid"

cd "$(dirname "$0")"

# Kill old watcher if exists
if [ -f "$WATCHER_PID_FILE" ]; then
    kill "$(cat $WATCHER_PID_FILE)" 2>/dev/null
    rm -f "$WATCHER_PID_FILE"
fi

# Kill old server
PID=$(lsof -ti tcp:$PORT 2>/dev/null)
[ -n "$PID" ] && kill "$PID" 2>/dev/null && sleep 0.3

start_server() {
    PID=$(lsof -ti tcp:$PORT 2>/dev/null)
    [ -n "$PID" ] && kill "$PID" 2>/dev/null && sleep 0.2
    nohup uv run python "$SCRIPT" > /tmp/dm-dashboard.log 2>&1 &
}

get_dir_mtime() {
    find tools/dm-dashboard -type f \( -name "*.py" -o -name "*.css" -o -name "*.html" \) \
        -exec stat -c %Y {} \; 2>/dev/null | sort | tail -1
}

start_server
sleep 0.5
echo "Dashboard: http://localhost:$PORT (hot-reload ON)"

# Background watcher: restart server when any .py/.css/.html in package changes
(
    LAST=$(get_dir_mtime)
    while true; do
        sleep 1
        NOW=$(get_dir_mtime)
        if [ "$NOW" != "$LAST" ]; then
            LAST=$NOW
            start_server
        fi
    done
) &
echo $! > "$WATCHER_PID_FILE"
