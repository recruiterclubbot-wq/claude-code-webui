FROM codercom/code-server:latest

USER root

# Install Python 3 and basic utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install official Anthropic Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Create workspace and app directories
RUN mkdir -p /app /home/coder/workspace /home/coder/.claude \
    && chown -R coder:coder /app /home/coder/workspace /home/coder/.claude

# Copy bridge and entrypoint
COPY bridge.py /app/bridge.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/bridge.py

USER coder

# Preconfigure VS Code User settings for low RAM and zero telemetry
RUN mkdir -p /home/coder/.local/share/code-server/User && \
    echo '{\n\
  "telemetry.telemetryLevel": "off",\n\
  "security.workspace.trust.enabled": false,\n\
  "workbench.startupEditor": "none",\n\
  "files.watcherExclude": {\n\
    "**/.git/objects/**": true,\n\
    "**/node_modules/**": true\n\
  }\n\
}' > /home/coder/.local/share/code-server/User/settings.json

# Preconfigure Claude Code settings
RUN echo '{\n\
  "env": {\n\
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:8082",\n\
    "ANTHROPIC_API_KEY": "google-pro-live"\n\
  }\n\
}' > /home/coder/.claude/settings.json

# Add environment variables to .bashrc for the integrated terminal
RUN echo '\nexport ANTHROPIC_BASE_URL="http://127.0.0.1:8082"\nexport ANTHROPIC_API_KEY="google-pro-live"\n' >> /home/coder/.bashrc

ENV PORT=10000
ENV BRIDGE_PORT=8082
ENV GEMINI_MODEL=gemini-3.5-flash
ENV NODE_OPTIONS="--max-old-space-size=256"

EXPOSE 10000

ENTRYPOINT ["/app/entrypoint.sh"]
