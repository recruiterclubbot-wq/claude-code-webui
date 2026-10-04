FROM node:20-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    curl \
    git \
    tar \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install official Microsoft VS Code CLI (standalone binary)
RUN curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output /tmp/vscode_cli.tar.gz \
    && tar -xf /tmp/vscode_cli.tar.gz -C /usr/local/bin \
    && rm /tmp/vscode_cli.tar.gz \
    && chmod +x /usr/local/bin/code

# Install official Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

# Create workspace and configuration directories
RUN mkdir -p /workspace /root/.claude /root/.vscode-cli

# Copy bridge and tunnel manager
COPY bridge.py /app/bridge.py
COPY tunnel_manager.py /app/tunnel_manager.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/bridge.py /app/tunnel_manager.py

ENV PORT=10000
ENV BRIDGE_PORT=8082
ENV GEMINI_MODEL=gemini-3.5-flash
ENV TUNNEL_NAME=claude-studio

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
