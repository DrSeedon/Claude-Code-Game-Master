#!/usr/bin/env bash
BACKEND_PORT=8800
FRONTEND_PORT=3000

cd "$(dirname "$0")"

# Kill old processes
for PORT in $BACKEND_PORT $FRONTEND_PORT; do
    PID=$(lsof -ti tcp:$PORT 2>/dev/null)
    [ -n "$PID" ] && kill "$PID" 2>/dev/null
done
sleep 0.3

# Start backend
nohup uv run uvicorn backend.server:app --host 0.0.0.0 --port $BACKEND_PORT > /tmp/dm-backend.log 2>&1 &
BACKEND_PID=$!

# Start frontend
cd frontend && nohup npx vite --port $FRONTEND_PORT > /tmp/dm-frontend.log 2>&1 &
cd ..
FRONTEND_PID=$!

sleep 2

# Verify
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "✅ Backend:  http://localhost:$BACKEND_PORT"
else
    echo "❌ Backend failed — see /tmp/dm-backend.log"
fi

if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "✅ Frontend: http://localhost:$FRONTEND_PORT"
else
    echo "❌ Frontend failed — see /tmp/dm-frontend.log"
fi

echo ""
echo "Logs: /tmp/dm-backend.log, /tmp/dm-frontend.log"
echo "Stop: kill $BACKEND_PID $FRONTEND_PID"
