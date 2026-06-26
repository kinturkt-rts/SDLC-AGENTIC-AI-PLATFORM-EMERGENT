# syntax=docker/dockerfile:1
# Shared ARM64 image for any SDLC agent runtime.
# Build from repository root:
#   docker buildx build --platform linux/arm64 \
#     -f deploy/agentcore/Dockerfile \
#     --build-arg AGENTCORE_AGENT=architect-agent \
#     --build-arg INSTALL_NODE=false \
#     -t sdlc-architect-agent:latest .

FROM --platform=linux/arm64 python:3.12-slim-bookworm

ARG AGENTCORE_AGENT=orchestrator-agent
ARG INSTALL_NODE=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "$INSTALL_NODE" = "true" ]; then \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
      && apt-get install -y --no-install-recommends nodejs \
      && rm -rf /var/lib/apt/lists/*; \
    fi

ENV REPO_ROOT=/app
ENV PYTHONUNBUFFERED=1
ENV AGENTCORE_A2A_HOST=0.0.0.0
ENV AGENTCORE_A2A_PORT=9000
ENV AGENTCORE_AGENT=${AGENTCORE_AGENT}

COPY deploy/agentcore /app/deploy/agentcore
RUN pip install --no-cache-dir -r /app/deploy/agentcore/requirements.txt

COPY agents /app/agents
COPY a2a /app/a2a
COPY scripts/postgres_mcp_entry.py /app/scripts/postgres_mcp_entry.py

WORKDIR /app/deploy/agentcore

EXPOSE 9000

CMD ["python", "a2a_server.py"]
