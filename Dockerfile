FROM node:20-bookworm-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    git \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Claude Code CLI and Claude Code Web UI globally
RUN npm install -g @anthropic-ai/claude-code claude-code-webui

# Copy bridge and startup scripts
COPY bridge.py /app/bridge.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh /app/bridge.py

# Create workspace directory
RUN mkdir -p /workspace

# Configuration
ENV PORT=10000
ENV BRIDGE_PORT=8082
ENV ANTHROPIC_BASE_URL=http://127.0.0.1:8082
ENV ANTHROPIC_API_KEY=google-pro-live
ENV GEMINI_MODEL=gemini-3.5-flash

EXPOSE 10000

CMD ["/app/entrypoint.sh"]
