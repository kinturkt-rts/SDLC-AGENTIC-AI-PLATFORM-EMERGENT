# Shared GitLab MCP for ECS Fargate (HTTP mode). Not the gitlab-agent AgentCore image.
# Build context: backend/deploy/gitlab-mcp-server/
#
#   docker build -t gitlab-mcp-server .
#   # or: backend/scripts/push-gitlab-mcp-ecr.ps1 -BuildFromDockerfile
FROM ghcr.io/jmrplens/gitlab-mcp-server:latest

EXPOSE 8080

# Inherit base ENTRYPOINT (gitlab-mcp-server). Override Juno GitLab URL for ECS.
CMD ["--http", "--http-addr=0.0.0.0:8080", "--gitlab-url=https://code.junodev.net"]
