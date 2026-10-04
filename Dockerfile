FROM node:20-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    git \
    curl \
    procps \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install official Code-Server (VS Code Web) and official Claude Code CLI
RUN npm install -g code-server @anthropic-ai/claude-code

# Create workspace and configuration directories
RUN mkdir -p /workspace /root/.claude /root/.local/share/code-server/User

# Copy configuration, bridge and entrypoint
COPY bridge.py /app/bridge.py
COPY entrypoint.sh /app/entrypoint.sh
COPY settings.json /root/.local/share/code-server/User/settings.json
RUN chmod +x /app/entrypoint.sh /app/bridge.py

ENV PORT=10000
ENV BRIDGE_PORT=8082
ENV GEMINI_MODEL=gemini-3.5-flash
ENV NODE_OPTIONS="--max-old-space-size=256"

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
