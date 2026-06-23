"""Deterministic git publish helpers for SDLC feature artifacts (monorepo)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_EXCLUDE_DIR_NAMES = frozenset(
    {".venv", "__pycache__", ".pytest_cache", "node_modules", ".git"}
)
_EXCLUDE_FILE_NAMES = frozenset({".env", ".coverage"})


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def slugify_feature(feature: str) -> str:
    return feature.strip().lower().replace("_", "-")


def should_include_file(path: Path) -> bool:
    if path.name in _EXCLUDE_FILE_NAMES:
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return not any(part in _EXCLUDE_DIR_NAMES for part in path.parts)


def collect_feature_artifact_paths(feature: str, *, root: Path | None = None) -> list[str]:
    """Return repo-relative paths to commit for one pipeline feature."""
    root = root or repo_root()
    slug = slugify_feature(feature)
    rel_paths: set[str] = set()

    app_dir = root / "target-apps" / slug
    if app_dir.is_dir():
        for file_path in app_dir.rglob("*"):
            if file_path.is_file() and should_include_file(file_path):
                rel_paths.add(file_path.relative_to(root).as_posix())

    for candidate in (
        root / "docs" / "PRD" / f"{slug}.md",
        root / "docs" / "design" / f"{slug}.md",
        root / "docs" / "diagrams" / "generated-diagrams" / f"{slug}.png",
        root / "agents" / "pipeline" / f"{slug}.context.json",
        root / "agents" / "pipeline" / f"{slug}.developer-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.qa-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.devops-handoff.json",
    ):
        if candidate.is_file():
            rel_paths.add(candidate.relative_to(root).as_posix())

    return sorted(rel_paths)


def default_branch_name(feature: str) -> str:
    return f"sdlc/{slugify_feature(feature)}"


def github_feature_branch(feature: str) -> str:
    """Branch name for showcase repo — one branch per app (e.g. training-compliance)."""
    return slugify_feature(feature)


def dest_path_for_showcase_repo(rel_path: str, slug: str) -> str:
    """Map platform monorepo paths to SDLC-Agentic-AI-Platform layout."""
    prefix = f"target-apps/{slug}/"
    if rel_path.startswith(prefix):
        return f"{slug}/{rel_path[len(prefix):]}"
    return rel_path


def collect_showcase_publish_files(
    feature: str,
    *,
    root: Path | None = None,
) -> list[dict[str, str]]:
    """Build {path, content} payloads for GitHub MCP push_files (showcase repo layout)."""
    import base64

    root = root or repo_root()
    slug = slugify_feature(feature)
    text_suffixes = {
        ".py",
        ".md",
        ".sql",
        ".txt",
        ".ini",
        ".json",
        ".example",
    }
    files: list[dict[str, str]] = []
    for rel in collect_feature_artifact_paths(slug, root=root):
        if rel.endswith(".devops-handoff.json"):
            continue
        src = root / rel
        data = src.read_bytes()
        dest = dest_path_for_showcase_repo(rel, slug)
        if src.suffix.lower() == ".png":
            content = base64.b64encode(data).decode("ascii")
        elif src.name == ".gitignore" or src.suffix.lower() in text_suffixes:
            content = data.decode("utf-8")
        else:
            content = base64.b64encode(data).decode("ascii")
        files.append({"path": dest, "content": content})
    return files


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _run_gh(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    gh = os.getenv("GH_PATH", "gh")
    return subprocess.run(
        [gh, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env=os.environ.copy(),
    )


def git_publish_feature(
    feature: str,
    *,
    branch: str | None = None,
    commit_message: str | None = None,
    push: bool = True,
    remote: str = "origin",
    root: Path | None = None,
) -> dict[str, object]:
    """Stage feature artifacts, commit on a branch, and optionally push to remote."""
    root = root or repo_root()
    slug = slugify_feature(feature)
    branch = branch or default_branch_name(slug)
    commit_message = commit_message or f"feat({slug}): SDLC pipeline output"

    paths = collect_feature_artifact_paths(slug, root=root)
    if not paths:
        return {
            "ok": False,
            "error": f"No publishable artifacts found for feature '{slug}'",
            "paths": [],
        }

    status = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=root)
    if status.returncode != 0:
        return {"ok": False, "error": "Not a git repository", "paths": paths}

    current = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    current_branch = (current.stdout or "").strip()

    checkout = _run_git(["checkout", "-B", branch], cwd=root)
    if checkout.returncode != 0:
        return {
            "ok": False,
            "error": f"git checkout failed: {checkout.stderr.strip()}",
            "paths": paths,
        }

    add = _run_git(["add", "--", *paths], cwd=root)
    if add.returncode != 0:
        _run_git(["checkout", current_branch], cwd=root)
        return {
            "ok": False,
            "error": f"git add failed: {add.stderr.strip()}",
            "paths": paths,
        }

    diff_cached = _run_git(["diff", "--cached", "--quiet"], cwd=root)
    if diff_cached.returncode == 0:
        result: dict[str, object] = {
            "ok": True,
            "branch": branch,
            "commit": None,
            "pushed": False,
            "message": "No changes to commit (already up to date on branch)",
            "paths": paths,
            "previousBranch": current_branch,
        }
    else:
        commit = _run_git(["commit", "-m", commit_message], cwd=root)
        if commit.returncode != 0:
            _run_git(["checkout", current_branch], cwd=root)
            return {
                "ok": False,
                "error": f"git commit failed: {commit.stderr.strip()}",
                "paths": paths,
            }
        sha = _run_git(["rev-parse", "HEAD"], cwd=root)
        result = {
            "ok": True,
            "branch": branch,
            "commit": (sha.stdout or "").strip(),
            "pushed": False,
            "message": commit_message,
            "paths": paths,
            "previousBranch": current_branch,
        }

    if push:
        push_res = _run_git(["push", "-u", remote, branch], cwd=root)
        if push_res.returncode != 0:
            result["ok"] = False
            result["error"] = f"git push failed: {push_res.stderr.strip()}"
        else:
            result["pushed"] = True
            result["remote"] = remote

    return result


def gh_create_pull_request(
    *,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
    draft: bool = False,
    root: Path | None = None,
) -> dict[str, object]:
    """Create a GitHub PR using the gh CLI (requires gh auth login)."""
    root = root or repo_root()
    args = [
        "pr",
        "create",
        "--repo",
        f"{owner}/{repo}",
        "--title",
        title,
        "--body",
        body,
        "--head",
        head,
        "--base",
        base,
    ]
    if draft:
        args.append("--draft")
    proc = _run_gh(args, cwd=root)
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip() or proc.stdout.strip()}
    url = (proc.stdout or "").strip()
    pr_number: int | None = None
    if "/pull/" in url:
        try:
            pr_number = int(url.rstrip("/").split("/")[-1])
        except ValueError:
            pr_number = None
    return {"ok": True, "url": url, "pullRequestNumber": pr_number}
