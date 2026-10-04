#!/bin/bash
set -e

echo "=== Starting Microsoft VS Code Tunnel Cloud Supervisor ==="
echo "Port: ${PORT:-10000}"
echo "Bridge Port: ${BRIDGE_PORT:-8082}"
echo "Tunnel Name: ${TUNNEL_NAME:-claude-studio}"

# 1. Configure Claude Code settings
mkdir -p /root/.claude /workspace
cat <<EOF > /root/.claude/settings.json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:${BRIDGE_PORT:-8082}",
    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-google-pro-live}"
  }
}
EOF

# 2. Export environment variables for shell / terminal
export ANTHROPIC_BASE_URL="http://127.0.0.1:${BRIDGE_PORT:-8082}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-google-pro-live}"
echo 'export ANTHROPIC_BASE_URL="http://127.0.0.1:8082"' >> /root/.bashrc
echo 'export ANTHROPIC_API_KEY="google-pro-live"' >> /root/.bashrc

# 3. Launch the Python Tunnel Manager & Web Control Portal
cd /workspace
exec python3 /app/tunnel_manager.py
