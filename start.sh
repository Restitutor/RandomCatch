#!/bin/bash

# Find the process running uv (if any)
PID=$(ps aux | grep "uv run" | grep -v grep | awk '{print $2}')

if [ -n "$PID" ]; then
    echo "Stopping old bot process ($PID)..."
    kill "$PID"
    sleep 2
else
    echo "No existing bot process found."
fi

echo "Starting new bot..."
uv run ./main.py
wait
