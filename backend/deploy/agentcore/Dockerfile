# AgentCore container image (linux/arm64). Build context: backend/ repo root.
#
# Every specialist runtime needs the full agents/_shared/ library (artifact_store,
# pipeline_context, sdlc_pipeline, env, runner, …) even though each container only
# sets AGENTCORE_AGENT to one bundle. COPY agents/ ships _shared plus all agent packages.
#
# Keep in sync: backend/Dockerfile and .bedrock_agentcore/*/Dockerfile
# Regenerate per-agent copies: scripts/sync-agentcore-dockerfiles.ps1
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim-bookworm

ARG AGENTCORE_AGENT=orchestrator-agent
ARG INSTALL_NODE=false
# AWS: run shared gitlab-mcp-server on ECS (HTTP) and set GITLAB_MCP_HTTP_URL on gitlab-agent.
# Local stdio fallback: build with --build-arg INSTALL_GITLAB_MCP_BINARY=true (gitlab-agent only).
ARG INSTALL_GITLAB_MCP_BINARY=false
ARG GITLAB_MCP_VERSION=v2.2.1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        graphviz \
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

ARG CACHE_BUST=1
COPY deploy/agentcore /app/deploy/agentcore
RUN pip install --no-cache-dir -r /app/deploy/agentcore/requirements.txt

# Full agents tree — includes agents/_shared/ required by every specialist + orchestrator.
COPY agents /app/agents
COPY a2a /app/a2a
COPY scripts /app/scripts
COPY config /app/config

RUN if [ "$INSTALL_GITLAB_MCP_BINARY" = "true" ]; then \
      mkdir -p /app/bin \
      && curl -fsSL \
          "https://github.com/jmrplens/gitlab-mcp-server/releases/download/${GITLAB_MCP_VERSION}/gitlab-mcp-server-linux-arm64" \
          -o /app/bin/gitlab-mcp-server \
      && chmod +x /app/bin/gitlab-mcp-server; \
    fi

ENV GITLAB_MCP_SERVER_PATH=/app/bin/gitlab-mcp-server

WORKDIR /app/deploy/agentcore

EXPOSE 9000

CMD ["python", "a2a_server.py"]
