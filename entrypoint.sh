#!/bin/bash
set -e

PORT="${PORT:-10000}"
BRIDGE_PORT="${BRIDGE_PORT:-8082}"

echo "=== Starting Official Code-Server (VS Code Web) + Claude Code ==="
echo "Binding Port: $PORT"
echo "Bridge Port: $BRIDGE_PORT"

# 1. Start Python Google Gemini Bridge in background
python3 /app/bridge.py &
BRIDGE_PID=$!
echo "Google Gemini Bridge started (PID: $BRIDGE_PID)"

# 2. Wait for bridge to accept connections
sleep 2

# 3. Configure Claude Code settings
cat <<EOF > /root/.claude/settings.json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:${BRIDGE_PORT}",
    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-google-pro-live}"
  }
}
EOF

# 4. Export environment variables for shell / terminal
export ANTHROPIC_BASE_URL="http://127.0.0.1:${BRIDGE_PORT}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-google-pro-live}"
echo 'export ANTHROPIC_BASE_URL="http://127.0.0.1:8082"' >> /root/.bashrc
echo 'export ANTHROPIC_API_KEY="google-pro-live"' >> /root/.bashrc

cd /workspace

# 5. Launch official code-server
echo "Launching code-server on 0.0.0.0:${PORT}..."
exec code-server \
  --bind-addr "0.0.0.0:${PORT}" \
  --auth none \
  --disable-telemetry \
  --disable-workspace-trust \
  /workspace
