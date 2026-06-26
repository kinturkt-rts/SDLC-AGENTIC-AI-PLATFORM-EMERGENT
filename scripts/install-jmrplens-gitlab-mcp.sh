#!/usr/bin/env bash
# Download jmrplens/gitlab-mcp-server release binary into repo bin/ (GitLab Free MCP).
set -euo pipefail

VERSION="${GITLAB_MCP_VERSION:-v2.2.1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="${REPO_ROOT}/bin"
mkdir -p "${BIN_DIR}"

ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64|amd64)
    ASSET="gitlab-mcp-server-linux-amd64"
    DEST="${BIN_DIR}/gitlab-mcp-server"
    ;;
  aarch64|arm64)
    ASSET="gitlab-mcp-server-linux-arm64"
    DEST="${BIN_DIR}/gitlab-mcp-server"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}" >&2
    exit 1
    ;;
esac

URL="https://github.com/jmrplens/gitlab-mcp-server/releases/download/${VERSION}/${ASSET}"
echo "Downloading ${URL}"
echo "  -> ${DEST}"
curl -fsSL "${URL}" -o "${DEST}"
chmod +x "${DEST}"
echo "Done."
