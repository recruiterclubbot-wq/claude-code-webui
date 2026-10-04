#!/bin/bash
set -e

PORT="${PORT:-10000}"
BRIDGE_PORT="${BRIDGE_PORT:-8082}"

echo "=== Starting Official Code-Server + Claude Code Cloud Studio ==="
echo "Binding Port: $PORT"
echo "Bridge Port: $BRIDGE_PORT"

# 1. Start Python Google Gemini Bridge in background
python3 /app/bridge.py &
BRIDGE_PID=$!
echo "Google Gemini Bridge started (PID: $BRIDGE_PID)"

# 2. Wait for bridge to accept connections
sleep 2

# 3. Export environment variables for all shells
export ANTHROPIC_BASE_URL="http://127.0.0.1:${BRIDGE_PORT}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-google-pro-live}"

cd /home/coder/workspace

# 4. Launch official code-server with low-RAM flags
echo "Launching code-server on 0.0.0.0:${PORT}..."
exec code-server \
  --bind-addr "0.0.0.0:${PORT}" \
  --auth none \
  --disable-telemetry \
  --disable-workspace-trust \
  /home/coder/workspace
