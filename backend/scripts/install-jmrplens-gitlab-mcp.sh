#!/usr/bin/env bash
# Download jmrplens/gitlab-mcp-server release binary into repo bin/ (GitLab Free MCP).
set -euo pipefail

VERSION="${GITLAB_MCP_VERSION:-v2.2.1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="${REPO_ROOT}/bin"
mkdir -p "${BIN_DIR}"

ARCH="$(uname -s)"
MACHINE="$(uname -m)"
case "${ARCH}" in
  Darwin)
    case "${MACHINE}" in
      x86_64) ASSET="gitlab-mcp-server-darwin-amd64" ;;
      arm64|aarch64) ASSET="gitlab-mcp-server-darwin-arm64" ;;
      *) echo "Unsupported macOS architecture: ${MACHINE}" >&2; exit 1 ;;
    esac
    DEST="${BIN_DIR}/gitlab-mcp-server"
    ;;
  Linux)
    case "${MACHINE}" in
      x86_64|amd64) ASSET="gitlab-mcp-server-linux-amd64" ;;
      aarch64|arm64) ASSET="gitlab-mcp-server-linux-arm64" ;;
      *) echo "Unsupported Linux architecture: ${MACHINE}" >&2; exit 1 ;;
    esac
    DEST="${BIN_DIR}/gitlab-mcp-server"
    ;;
  *)
    echo "Unsupported OS: ${ARCH}" >&2
    exit 1
    ;;
esac

URL="https://github.com/jmrplens/gitlab-mcp-server/releases/download/${VERSION}/${ASSET}"
echo "Downloading ${URL}"
echo "  -> ${DEST}"
curl -fsSL "${URL}" -o "${DEST}"
chmod +x "${DEST}"
echo "Done."
