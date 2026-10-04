#!/bin/bash
set -e

echo "=== Starting Microsoft VS Code Tunnel Cloud Supervisor ==="
echo "Port: ${PORT:-10000}"
echo "Bridge Port: ${BRIDGE_PORT:-8082}"
echo "Tunnel Name: ${TUNNEL_NAME:-claude-studio}"

# 1. Configure Claude Code settings to use our Antigravity Master Server
mkdir -p /root/.claude /workspace
cat <<EOF > /root/.claude/settings.json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://agent-master-server.onrender.com",
    "ANTHROPIC_API_KEY": "sk-antigravity-master-roman"
  }
}
EOF

# 2. Export environment variables for shell / terminal
export ANTHROPIC_BASE_URL="https://agent-master-server.onrender.com"
export ANTHROPIC_API_KEY="sk-antigravity-master-roman"
echo 'export ANTHROPIC_BASE_URL="https://agent-master-server.onrender.com"' >> /root/.bashrc
echo 'export ANTHROPIC_API_KEY="sk-antigravity-master-roman"' >> /root/.bashrc

# 3. Launch the Python Tunnel Manager & Web Control Portal
cd /workspace
exec python3 /app/tunnel_manager.py
