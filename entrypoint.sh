#!/bin/bash
set -e

echo "=== Starting Claude Code Web UI Cloud Environment ==="
echo "Render Port: ${PORT:-10000}"
echo "Bridge Port: ${BRIDGE_PORT:-8082}"

# 1. Initialize Claude configuration and default project
mkdir -p /root/.claude/projects/-workspace /workspace
echo '{"projects": {"/workspace": {}}}' > /root/.claude.json
cat <<EOF > /root/.claude/settings.json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:${BRIDGE_PORT:-8082}",
    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-google-pro-live}"
  }
}
EOF

# 2. Start the internal Google Gemini Bridge proxy
python3 /app/bridge.py &
BRIDGE_PID=$!
echo "Google Gemini Bridge started (PID: $BRIDGE_PID)"

# 3. Wait for bridge to accept connections
sleep 2

# Export environment variables for child processes
export ANTHROPIC_BASE_URL="http://127.0.0.1:${BRIDGE_PORT:-8082}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-google-pro-live}"

cd /workspace

echo "Starting Claude Code Web UI server on 0.0.0.0:${PORT:-10000}..."
exec claude-code-webui --host 0.0.0.0 --port "${PORT:-10000}"
