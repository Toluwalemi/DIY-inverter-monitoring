#!/usr/bin/env bash
# Start the inverter monitoring stack.
# Run reader.py in background, then launch dashboard in foreground.

cd "$(dirname "$0")"

echo "[run.sh] Starting inverter reader in background..."
python3 reader.py &
READER_PID=$!
echo "[run.sh] reader.py PID: $READER_PID"

echo "[run.sh] Starting Flask dashboard on port 5000..."
python3 dashboard.py

# If dashboard exits, also stop the reader
kill "$READER_PID" 2>/dev/null
