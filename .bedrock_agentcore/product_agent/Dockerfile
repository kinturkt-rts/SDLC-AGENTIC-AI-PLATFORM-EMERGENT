# AgentCore CodeBuild Dockerfile (sync with deploy/agentcore/Dockerfile).
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim-bookworm

ARG AGENTCORE_AGENT=product-agent
ARG GITLAB_MCP_VERSION=v2.2.1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        graphviz \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

ENV REPO_ROOT=/app
ENV PYTHONUNBUFFERED=1
ENV AGENTCORE_A2A_HOST=0.0.0.0
ENV AGENTCORE_A2A_PORT=9000
ENV AGENTCORE_AGENT=${AGENTCORE_AGENT}
ENV GITLAB_MCP_SERVER_PATH=/app/bin/gitlab-mcp-server

COPY deploy/agentcore /app/deploy/agentcore
RUN pip install --no-cache-dir -r /app/deploy/agentcore/requirements.txt

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
