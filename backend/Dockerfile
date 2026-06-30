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
ENV GITLAB_MCP_SERVER_PATH=/app/bin/gitlab-mcp-server

COPY deploy/agentcore /app/deploy/agentcore
RUN pip install --no-cache-dir -r /app/deploy/agentcore/requirements.txt

# Full agents tree — includes agents/_shared/ required by every specialist + orchestrator.
COPY agents /app/agents
COPY a2a /app/a2a
COPY scripts /app/scripts
COPY config /app/config

RUN mkdir -p /app/bin \
    && curl -fsSL \
        "https://github.com/jmrplens/gitlab-mcp-server/releases/download/${GITLAB_MCP_VERSION}/gitlab-mcp-server-linux-arm64" \
        -o /app/bin/gitlab-mcp-server \
    && chmod +x /app/bin/gitlab-mcp-server

WORKDIR /app/deploy/agentcore

EXPOSE 9000

CMD ["python", "a2a_server.py"]
