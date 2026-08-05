"""GitLab MCP actions: env config, CLI helpers, and SDLC publish workflow."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import httpx

from .gitlab_mcp_client import (
    GitLabMcpError,
    _list_repository_tree_async,
    call_gitlab_mcp_tool,
    gitlab_mcp_publish_url_candidates,
    gitlab_mcp_session,
    gitlab_mcp_uses_cloudfront,
    list_existing_blob_paths,
    use_gitlab_mcp_http,
    using_gitlab_mcp_url,
)

_DEFAULT_API_URL = "https://code.junodev.net/api/v4"
_DEFAULT_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform"
_DEFAULT_APPS_PROJECT_PATH = "junolabs/sdlc-agentic-ai-platform/sdlc-agentic-ai-platform-apps"
_BATCH_SIZE = 20
_HTTP_FILE_API_HINT = (
    "CloudFront/WAF returned 403 on the MCP POST body. "
    "Set GITLAB_MCP_HTTP_DIRECT_URL to the ALB /mcp URL (see config/agentcore/gitlab-mcp-endpoints.json)."
)

_WAF_LOCALHOST_HTTP = re.compile(r"https?://localhost(?=[:/])", re.IGNORECASE)


def sanitize_publish_content_for_waf(content: str) -> str:
    """Replace substrings that commonly trigger CloudFront/WAF on MCP POST bodies."""
    if not gitlab_mcp_uses_cloudfront():
        return content

    def _replace(match: re.Match[str]) -> str:
        scheme = match.group(0).split("://", 1)[0].lower()
        return f"{scheme}://127.0.0.1"

    return _WAF_LOCALHOST_HTTP.sub(_replace, content)


def _decode_publish_text(item: dict[str, Any]) -> str | None:
    """Return UTF-8 text for a publish payload (plain or base64-encoded)."""
    content = item.get("content")
    if not isinstance(content, str):
        return None
    if item.get("binary") or str(item.get("encoding") or "").lower() == "base64":
        try:
            return base64.b64decode(content).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return content


def _find_lone_surrogate_consts(code: Any, *, _seen: set[int] | None = None) -> list[str]:
    """Recursively scan a code object's string constants for lone UTF-16 surrogates.

    Python's `\\uD83C\\uDF93`-style escapes decode into two standalone surrogate
    *code points* rather than combining into one astral character the way
    JS/JSON do — `py_compile` happily accepts this (it's valid Python syntax),
    but the resulting `str` can never be UTF-8 encoded. Streamlit hits exactly
    this in `st.set_page_config(page_icon=...)`, so this has to be caught
    before publish, not left to blow up at runtime in production.
    """
    if _seen is None:
        _seen = set()
    if id(code) in _seen:
        return []
    _seen.add(id(code))

    bad: list[str] = []
    for const in code.co_consts:
        if isinstance(const, str):
            try:
                const.encode("utf-8")
            except UnicodeEncodeError:
                bad.append(repr(const))
        elif hasattr(const, "co_consts"):
            bad.extend(_find_lone_surrogate_consts(const, _seen=_seen))
    return bad


def assert_publish_python_syntax(files: list[dict[str, Any]]) -> None:
    """Fail publish early if any .py payload has a SyntaxError or an unencodable
    string constant (avoids green CI + 502/500 UI at runtime)."""
    import py_compile
    import tempfile

    errors: list[str] = []
    for item in files:
        path = str(item.get("path") or "")
        if not path.endswith(".py"):
            continue
        text = _decode_publish_text(item)
        if text is None:
            errors.append(f"{path}: could not decode publish payload as UTF-8 Python source")
            continue
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".py",
            encoding="utf-8",
            delete=False,
            newline="",
        ) as tmp:
            tmp.write(text)
            tmp_path = tmp.name
        try:
            py_compile.compile(tmp_path, doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{path}: {exc.msg}")
        else:
            try:
                code = compile(text, path, "exec")
            except SyntaxError:
                code = None  # already reported above via py_compile
            if code is not None:
                lone_surrogates = _find_lone_surrogate_consts(code)
                for bad_repr in lone_surrogates:
                    errors.append(
                        f"{path}: string constant {bad_repr} contains a lone UTF-16 "
                        "surrogate (from a \\uD800-\\uDFFF escape) and cannot be "
                        "UTF-8 encoded — use the literal Unicode character or a "
                        "single \\Uxxxxxxxx escape instead"
                    )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if errors:
        raise ValueError(
            "Refusing to publish Python that would crash at runtime:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def _build_publish_file(dest_rel: str, data: bytes) -> dict[str, Any]:
    """Build one GitLab publish payload.

    Python sources are always base64. The MCP/text JSON path expands literal
    ``\\n`` sequences into real newlines, which turns golden files like
    ``app/startup_checks.py`` into byte-identical SyntaxErrors across every app.
    Base64 + ``encoding=base64`` on file_create/update preserves bytes exactly
    (same path already used for PNGs).
    """
    suffix = Path(dest_rel).suffix.lower()
    name = Path(dest_rel).name
    if suffix == ".py" or suffix == ".png":
        return {
            "path": dest_rel,
            "content": base64.b64encode(data).decode("ascii"),
            "binary": True,
        }
    # Include .yml/.yaml so apps-repo .gitlab-ci.yml publishes as text (not
    # base64 binary) — binary uploads were silently unreliable for this path.
    text_suffixes = {".md", ".sql", ".txt", ".ini", ".json", ".example", ".yml", ".yaml"}
    if name == ".gitignore" or name == ".gitlab-ci.yml" or suffix in text_suffixes:
        return {
            "path": dest_rel,
            "content": sanitize_publish_content_for_waf(data.decode("utf-8")),
            "binary": False,
        }
    return {
        "path": dest_rel,
        "content": base64.b64encode(data).decode("ascii"),
        "binary": True,
    }


def _publish_batch_size() -> int:
    """CloudFront/WAF: one file per request. Direct ALB: batched commits (default 20)."""
    if use_gitlab_mcp_http():
        default = "1" if gitlab_mcp_uses_cloudfront() else str(_BATCH_SIZE)
        raw = os.getenv("GITLAB_MCP_HTTP_BATCH_SIZE", default).strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return 1 if gitlab_mcp_uses_cloudfront() else _BATCH_SIZE
    return _BATCH_SIZE

PublishLayout = Literal["monorepo", "apps"]

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


def _load_developer_handoff_written_paths(slug: str, root: Path) -> list[str]:
    """Return monorepo-relative paths listed in developer-handoff.json."""
    candidates = (
        root / slug / "handoffs" / "developer-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.developer-handoff.json",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        written = data.get("writtenFiles") or []
        return [item for item in written if isinstance(item, str) and item.strip()]
    return []


def _workspace_source_for_repo_rel(slug: str, root: Path, repo_rel: str) -> Path | None:
    """Resolve a materialized workspace file for a monorepo-relative target-apps path."""
    normalized = repo_rel.replace("\\", "/").lstrip("/")
    prefix = f"target-apps/{slug}/"
    candidates: list[Path] = []
    if normalized.startswith(prefix):
        tail = normalized[len(prefix) :]
        candidates.append(root / slug / tail)
    candidates.append(root / normalized)
    for candidate in candidates:
        if candidate.is_file() and should_include_file(candidate):
            return candidate
    return None


def _entry_for_workspace_file(slug: str, root: Path, source: Path) -> tuple[str, str] | None:
    """Map a workspace file to (source_rel, gitlab_dest_rel)."""
    try:
        workspace_rel = source.relative_to(root).as_posix()
    except ValueError:
        return None
    if is_cloud_materialized_workspace(root, slug):
        dest = cloud_workspace_to_gitlab_dest(slug, workspace_rel)
        if not dest:
            return None
        return workspace_rel, dest
    return workspace_rel, workspace_rel


def _merge_developer_handoff_entries(
    slug: str,
    root: Path,
    entries: set[tuple[str, str]],
) -> None:
    """Include developer-handoff writtenFiles so late S3 writes are not dropped."""
    for repo_rel in _load_developer_handoff_written_paths(slug, root):
        source = _workspace_source_for_repo_rel(slug, root, repo_rel)
        if source is None:
            continue
        mapped = _entry_for_workspace_file(slug, root, source)
        if mapped:
            entries.add(mapped)


def is_cloud_materialized_workspace(root: Path, slug: str) -> bool:
    """True when *root* is a materialized S3 run dir (``<slug>/...``), not local monorepo."""
    if (root / "target-apps" / slug).is_dir():
        return False
    return (root / slug).is_dir()


def cloud_workspace_to_gitlab_dest(slug: str, workspace_rel: str) -> str | None:
    """Map a materialized cloud artifact path to monorepo GitLab destination path."""
    normalized = workspace_rel.replace("\\", "/").lstrip("/")
    prefix = f"{slug}/"
    if not normalized.startswith(prefix):
        return None
    tail = normalized[len(prefix) :]
    if not tail or tail.startswith("telemetry/") or tail.startswith("events/"):
        # Telemetry + agent activity events stay in S3 for the control plane —
        # not part of the apps-repo deliverable.
        return None

    if tail.startswith("inputs/"):
        name = Path(tail).name
        if name.endswith(".txt"):
            return f"inputs/{name}"
        return None

    if tail == "context.json":
        return f"agents/pipeline/{slug}.context.json"

    if tail == "frontend-handoff.json":
        return f"agents/pipeline/{slug}.frontend-handoff.json"

    if tail.startswith("handoffs/"):
        handoff_map = {
            "developer-handoff.json": f"agents/pipeline/{slug}.developer-handoff.json",
            "gitlab-handoff.json": f"agents/pipeline/{slug}.gitlab-handoff.json",
            "qa-handoff.json": f"agents/pipeline/{slug}.qa-handoff.json",
            "devops-handoff.json": f"agents/pipeline/{slug}.devops-handoff.json",
            "database-handoff.md": f"agents/pipeline/{slug}.database-handoff.md",
            "frontend-handoff.json": f"agents/pipeline/{slug}.frontend-handoff.json",
        }
        return handoff_map.get(Path(tail).name)

    if tail.startswith("docs/PRD/") or tail.startswith("docs/design/"):
        return tail

    if tail.startswith("docs/generated-diagrams/"):
        return tail

    if tail.startswith("docs/diagrams/"):
        return f"docs/generated-diagrams/{Path(tail).name}"

    return f"target-apps/{slug}/{tail}"


def _merge_input_brief_entries(
    slug: str,
    root: Path,
    entries: set[tuple[str, str]],
) -> None:
    """Attach inputs/<brief>.txt for monorepo and apps publish layouts."""
    for source_rel, dest_rel in _collect_input_brief_entries(slug, root=root):
        entries.add((source_rel, dest_rel))


def collect_feature_artifact_entries(
    feature: str,
    *,
    root: Path | None = None,
) -> list[tuple[str, str]]:
    """Return ``(workspace_source_rel, gitlab_dest_rel)`` pairs to publish."""
    root = root or repo_root()
    slug = slugify_feature(feature)

    if is_cloud_materialized_workspace(root, slug):
        entries: set[tuple[str, str]] = set()
        cloud_root = root / slug
        for file_path in cloud_root.rglob("*"):
            if not file_path.is_file() or not should_include_file(file_path):
                continue
            source = file_path.relative_to(root).as_posix()
            dest = cloud_workspace_to_gitlab_dest(slug, source)
            if dest:
                entries.add((source, dest))
        _merge_developer_handoff_entries(slug, root, entries)
        _merge_input_brief_entries(slug, root, entries)
        return sorted(entries, key=lambda item: item[1])

    entries = {
        (rel, rel)
        for rel in _collect_local_monorepo_artifact_paths(feature, root=root)
    }
    _merge_developer_handoff_entries(slug, root, entries)
    _merge_input_brief_entries(slug, root, entries)
    return sorted(entries, key=lambda item: item[1])


def collect_feature_artifact_paths(feature: str, *, root: Path | None = None) -> list[str]:
    """Return repo-relative GitLab destination paths for one SDLC feature."""
    return [dest for _, dest in collect_feature_artifact_entries(feature, root=root)]


def _collect_local_monorepo_artifact_paths(feature: str, *, root: Path | None = None) -> list[str]:
    """Local monorepo layout: ``target-apps/<slug>/``, ``docs/PRD/``, pipeline handoffs."""
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
        root / "docs" / "generated-diagrams" / f"{slug}.png",
        root / "docs" / "diagrams" / "generated-diagrams" / f"{slug}.png",
        root / "agents" / "pipeline" / f"{slug}.context.json",
        root / "agents" / "pipeline" / f"{slug}.developer-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.qa-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.devops-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.gitlab-handoff.json",
        root / "agents" / "pipeline" / f"{slug}.database-handoff.md",
    ):
        if candidate.is_file():
            rel_paths.add(candidate.relative_to(root).as_posix())

    return sorted(rel_paths)


def default_branch_name(feature: str) -> str:
    return f"sdlc/{slugify_feature(feature)}"


def apps_branch_name(feature: str) -> str:
    """Branch name for sdlc-agentic-ai-platform-apps (matches CI ``^sdlc/`` rules)."""
    return default_branch_name(feature)


def pipeline_run_marker_repo_rel(feature: str) -> str:
    """Monorepo-relative path for the CI pipeline-run marker under a target app."""
    return f"target-apps/{slugify_feature(feature)}/.sdlc/pipeline-run.json"


def write_pipeline_run_marker(
    feature: str,
    run_id: str,
    *,
    root: Path | None = None,
) -> str | None:
    """Write ``.sdlc/pipeline-run.json`` so GitLab CI can export ``PIPELINE_RUN_ID``.

    Also records ``artifactS3Bucket`` from ``ARTIFACT_S3_BUCKET`` when set so the
    shared apps-repo CI can write devops handoffs back to the correct env bucket
    (dev vs demo) without changing group-level CI/CD defaults.

    Returns the monorepo-relative path written, or ``None`` when skipped (no run id /
    no app tree). Works for local monorepo and cloud-materialized workspaces.
    """
    rid = (run_id or "").strip()
    if not rid:
        return None
    root = root or repo_root()
    slug = slugify_feature(feature)
    payload: dict[str, Any] = {
        "runId": rid,
        "targetApp": slug,
        "writtenBy": "gitlab-agent",
    }
    # Optional: pin the artifact store for the async GitLab CI → devops step.
    # Older markers omit this; CI falls back to the group ARTIFACT_S3_BUCKET var.
    bucket = (os.getenv("ARTIFACT_S3_BUCKET") or "").strip()
    if bucket:
        payload["artifactS3Bucket"] = bucket
    text = json.dumps(payload, indent=2) + "\n"

    if is_cloud_materialized_workspace(root, slug):
        app_root = root / slug
        if not app_root.is_dir():
            return None
        path = app_root / ".sdlc" / "pipeline-run.json"
    else:
        app_root = root / "target-apps" / slug
        if not app_root.is_dir():
            return None
        path = app_root / ".sdlc" / "pipeline-run.json"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return pipeline_run_marker_repo_rel(slug)


def dest_path_for_apps_repo(rel_path: str, slug: str) -> str | None:
    """Map monorepo-relative paths to the apps-repo branch layout:
    ``<slug>/backend/**`` for the FastAPI/db source tree, ``<slug>/frontend/**``
    for the UI (React ``frontend/`` or legacy Streamlit ``ui/``); ``docs/``,
    ``agents/pipeline/``, ``.sdlc/`` marker, and ``inputs/*.txt`` are unchanged at
    branch root (PRD/design/diagram docs and pipeline handoffs live alongside
    backend/frontend, not nested under either).
    """
    if rel_path.startswith("inputs/") and rel_path.endswith(".txt"):
        return rel_path
    if rel_path.startswith("docs/") or rel_path.startswith("agents/pipeline/"):
        return rel_path
    prefix = f"target-apps/{slug}/"
    if not rel_path.startswith(prefix):
        return None
    tail = rel_path[len(prefix) :]
    if tail.startswith(".sdlc/"):
        return tail
    # Operational / control-plane only — never nest under backend in apps repo.
    if tail.startswith("events/") or tail.startswith("telemetry/"):
        return None
    if tail == "frontend-handoff.json":
        return f"agents/pipeline/{slug}.frontend-handoff.json"
    # React UI (sibling of backend) — must not fall through to backend/frontend/.
    if tail.startswith("frontend/"):
        return f"{slug}/frontend/{tail[len('frontend/') :]}"
    # Legacy Streamlit UI folder → same apps-repo frontend/ destination.
    if tail.startswith("ui/"):
        return f"{slug}/frontend/{tail[len('ui/') :]}"
    return f"{slug}/backend/{tail}"


def _apps_backend_readme_text(content: str, slug: str) -> str:
    """Rewrite monorepo ``target-apps/<slug>`` paths for apps-repo sibling layout."""
    body = content.replace(f"target-apps/{slug}", f"{slug}/backend")
    banner = (
        f"# {slug}\n\n"
        f"Apps-repo layout on this branch:\n\n"
        f"- `{slug}/backend/` — FastAPI API, DB SQL, tests (this folder)\n"
        f"- `{slug}/frontend/` — Vite/React UI "
        f"(see `{slug}/frontend/README.md`)\n\n"
        f"Pipeline handoffs live under `agents/pipeline/` at the repo root.\n\n"
        f"---\n\n"
    )
    if "Apps-repo layout on this branch" in body:
        return body
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        body = "\n".join(lines[1:]).lstrip("\n")
    return banner + body


def _apps_frontend_readme_text(slug: str) -> str:
    return (
        f"# {slug} frontend\n\n"
        f"Vite + React UI for `{slug}`.\n\n"
        f"## Run locally\n\n"
        f"```bash\n"
        f"cd {slug}/frontend\n"
        f"cp .env.example .env   # if present; set VITE_API_URL to the API base\n"
        f"npm install\n"
        f"npm run dev\n"
        f"```\n\n"
        f"API lives in the sibling folder `{slug}/backend/` "
        f"(uvicorn — see that README).\n"
    )


def _input_brief_candidate_rels(slug: str, root: Path) -> list[str]:
    """Repo-relative input brief paths to try (context inputFile, then slug default).

    Reads via read_context_json (utf-8-sig) so a BOM on an existing
    context.json (PS 5.1's Update-Context always writes one) no longer looks
    like a parse failure and silently sends this straight to the
    filename-guess fallback below. A genuine OSError (file vanished, no
    permission) still just moves on to the next candidate path; a genuine
    json.JSONDecodeError (real corruption) is allowed to propagate instead of
    being masked the same way.
    """
    from _shared.pipeline_context import read_context_json

    rels: list[str] = []
    for ctx_path in (
        root / slug / "context.json",
        root / "agents" / "pipeline" / f"{slug}.context.json",
    ):
        if not ctx_path.is_file():
            continue
        try:
            data = read_context_json(ctx_path)
        except OSError:
            continue
        for key in ("inputFile", "inputPath"):
            val = data.get(key)
            if isinstance(val, str) and val.strip().startswith("inputs/"):
                rels.append(val.strip().replace("\\", "/"))
    rels.append(f"inputs/{slug}.txt")
    return list(dict.fromkeys(rels))


def _collect_input_brief_entries(slug: str, *, root: Path) -> list[tuple[str, str]]:
    """Input briefs for apps-repo publish: (workspace_source_rel, inputs/<file>.txt)."""
    entries: list[tuple[str, str]] = []
    seen_dest: set[str] = set()

    def _add(source: Path, dest: str) -> None:
        if dest in seen_dest or not source.is_file() or not should_include_file(source):
            return
        try:
            source_rel = source.relative_to(root).as_posix()
        except ValueError:
            return
        seen_dest.add(dest)
        entries.append((source_rel, dest))

    cloud_inputs = root / slug / "inputs"
    if cloud_inputs.is_dir():
        for file_path in sorted(cloud_inputs.glob("*.txt")):
            _add(file_path, f"inputs/{file_path.name}")

    for rel in _input_brief_candidate_rels(slug, root):
        _add(root / rel, rel)

    return entries


def gitlab_personal_access_token() -> str:
    for key in ("GITLAB_PERSONAL_ACCESS_TOKEN", "GITLAB_TOKEN", "GL_TOKEN"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise ValueError(
        "GITLAB_PERSONAL_ACCESS_TOKEN is not set. Add a GitLab PAT to .env "
        "(scopes: api, read_api, read_repository, write_repository)."
    )


def gitlab_api_url() -> str:
    return (os.getenv("GITLAB_API_URL") or _DEFAULT_API_URL).strip().rstrip("/")


def gitlab_project_path() -> str:
    return (
        os.getenv("GITLAB_PROJECT_PATH")
        or os.getenv("GITLAB_PROJECT_ID")
        or _DEFAULT_PROJECT_PATH
    ).strip()


def gitlab_base_branch() -> str:
    return (os.getenv("GITLAB_BASE_BRANCH") or "main").strip() or "main"


def gitlab_apps_project_path() -> str:
    return (os.getenv("GITLAB_APPS_PROJECT_PATH") or _DEFAULT_APPS_PROJECT_PATH).strip()


def _mcp_error_message(exc: BaseException) -> str:
    """Extract a useful message from GitLabMcpError or nested ExceptionGroup wrappers."""
    if isinstance(exc, GitLabMcpError):
        return str(exc)
    if isinstance(exc, BaseExceptionGroup):
        for nested in exc.exceptions:
            msg = _mcp_error_message(nested)
            if msg and msg != str(exc):
                return msg
    message = str(exc)
    if "403 Forbidden" in message and "cloudfront.net/mcp" in message.lower():
        return f"{message}\n\n{_HTTP_FILE_API_HINT}"
    return message


def _is_branch_not_found(exc: BaseException) -> bool:
    message = _mcp_error_message(exc).lower()
    return "branch" in message and "not found" in message


def _run(coro: Any) -> dict[str, Any]:
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running (CLI / local pipeline) — safe to use asyncio.run().
            return asyncio.run(coro)
        # Already inside an event loop (e.g. AgentCore A2A server). asyncio.run() would raise
        # "cannot be called from a running event loop", so drive the coroutine to completion on a
        # dedicated loop in a worker thread instead.
        box: dict[str, Any] = {}

        def _worker() -> None:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                box["value"] = loop.run_until_complete(coro)
            except BaseException as exc:  # noqa: BLE001 - surfaced via box["error"]
                box["error"] = exc
            finally:
                asyncio.set_event_loop(None)
                loop.close()

        thread = threading.Thread(target=_worker, name="gitlab-mcp-publish")
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box["value"]
    except BaseException as exc:
        return {"ok": False, "error": _mcp_error_message(exc)}


# --- Repo config & publish helpers ---


def publish_branch_name(feature: str) -> str:
    """One stable branch per target app; republishs update files on the same branch."""
    return default_branch_name(feature)


def _branch_tree_url(web_url: str, branch: str) -> str:
    """GitLab branch browse URL.

    Prefer an unencoded path segment (``sdlc/app``) plus ``ref_type=heads``.
    Encoded forms like ``sdlc%2Fapp`` work less reliably in the GitLab UI.
    """
    base = web_url.rstrip("/")
    branch_path = branch.strip().lstrip("/")
    return f"{base}/-/tree/{branch_path}?ref_type=heads"


def gitlab_repo_config(
    *,
    project: str | None = None,
    base_branch: str | None = None,
) -> dict[str, str]:
    return {
        "project": (project or gitlab_project_path()).strip(),
        "base": (base_branch or gitlab_base_branch()).strip() or "main",
    }


def _batch_files(
    files: list[dict[str, Any]], batch_size: int | None = None
) -> list[list[dict[str, Any]]]:
    size = batch_size if batch_size is not None else _publish_batch_size()
    return [files[i : i + size] for i in range(0, len(files), size)]


def _mr_body(slug: str, paths: list[str]) -> str:
    lines = "\n".join(f"- `{p}`" for p in paths[:40])
    extra = f"\n- … and {len(paths) - 40} more" if len(paths) > 40 else ""
    return (
        f"Automated SDLC pipeline output for **{slug}**.\n\n"
        f"## Artifacts\n{lines}{extra}\n\n"
        f"## Docs\n"
        f"- [PRD](docs/PRD/{slug}.md)\n"
        f"- [Design](docs/design/{slug}.md)\n"
    )


def _collect_monorepo_publish_files(feature: str, *, root: Any | None = None) -> list[dict[str, Any]]:
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    files: list[dict[str, Any]] = []
    for source_rel, dest_rel in collect_feature_artifact_entries(slug, root=root_path):
        if dest_rel.endswith(".devops-handoff.json"):
            continue
        src = root_path / source_rel
        files.append(_build_publish_file(dest_rel, src.read_bytes()))
    return files


def resolve_apps_repo_ci_template(root: Path | None = None) -> Path | None:
    """Locate the apps-repo deploy CI template for every publish.

    Prefer the copy shipped beside this module (``agents/_shared/``) — that path
    is always inside ``COPY agents`` for AgentCore. Then fall back to
    ``scripts/gitlab-apps-repo-ci.yml`` under the publish root / backend root.
    """
    candidates: list[Path] = [
        Path(__file__).resolve().parent / "gitlab_apps_repo_ci.yml",
    ]
    if root is not None:
        candidates.append(Path(root) / "scripts" / "gitlab-apps-repo-ci.yml")
    candidates.append(repo_root() / "scripts" / "gitlab-apps-repo-ci.yml")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _collect_apps_repo_publish_files(feature: str, *, root: Any | None = None) -> list[dict[str, Any]]:
    """Publish <slug>/backend/ + <slug>/frontend/ at branch root plus inputs/<brief>.txt (apps GitLab project)."""
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    seen_dest: set[str] = set()
    publish_entries: list[tuple[str, str]] = []

    for source_rel, dest_rel in collect_feature_artifact_entries(slug, root=root_path):
        dest = dest_path_for_apps_repo(dest_rel, slug)
        if dest is None or dest in seen_dest:
            continue
        seen_dest.add(dest)
        publish_entries.append((source_rel, dest))

    for source_rel, dest_rel in _collect_input_brief_entries(slug, root=root_path):
        dest = dest_path_for_apps_repo(dest_rel, slug)
        if dest is None or dest in seen_dest:
            continue
        seen_dest.add(dest)
        publish_entries.append((source_rel, dest))

    files: list[dict[str, Any]] = []
    has_frontend = False
    for source_rel, dest in publish_entries:
        src = root_path / source_rel
        data = src.read_bytes()
        if dest == f"{slug}/backend/README.md":
            text = _apps_backend_readme_text(data.decode("utf-8"), slug)
            files.append(_build_publish_file(dest, text.encode("utf-8")))
        else:
            files.append(_build_publish_file(dest, data))
        if dest.startswith(f"{slug}/frontend/"):
            has_frontend = True

    frontend_readme_dest = f"{slug}/frontend/README.md"
    if has_frontend and frontend_readme_dest not in seen_dest:
        seen_dest.add(frontend_readme_dest)
        files.append(
            _build_publish_file(
                frontend_readme_dest,
                _apps_frontend_readme_text(slug).encode("utf-8"),
            )
        )

    # ALWAYS overwrite .gitlab-ci.yml on the apps branch with the platform
    # temp-fix template (MCR image). Inheritance from default branch only
    # happens at branch creation — without this, branches keep the old ECR image.
    ci_template = resolve_apps_repo_ci_template(root_path)
    if ci_template is None:
        raise FileNotFoundError(
            "apps-repo CI template missing: expected agents/_shared/gitlab_apps_repo_ci.yml "
            "or scripts/gitlab-apps-repo-ci.yml (required so every publish uses the "
            "working MCR deploy image, not private ECR sdlc-deploy-ci)"
        )
    ci_bytes = ci_template.read_bytes()
    ci_item = _build_publish_file(".gitlab-ci.yml", ci_bytes)
    # Put CI first so early pipeline commits already use the correct image.
    files.insert(0, ci_item)
    print(
        f"[gitlab-mcp] apps publish will overwrite .gitlab-ci.yml "
        f"from {ci_template} ({len(ci_bytes)} bytes, binary={ci_item.get('binary')})",
        flush=True,
    )

    return files


def _split_publish_files(files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text_files: list[dict[str, Any]] = []
    binary_files: list[dict[str, Any]] = []
    for item in files:
        if item.get("binary"):
            binary_files.append(item)
        else:
            text_files.append(item)
    return text_files, binary_files


def _commit_content(content: str) -> str:
    """GitLab requires content on create/update; jmrplens omits empty strings from JSON."""
    return content if content else "\n"


def _commit_actions(
    batch: list[dict[str, Any]],
    existing_paths: set[str],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for item in batch:
        path = item["path"].lstrip("/")
        action: dict[str, Any] = {
            "action": "update" if path in existing_paths else "create",
            "file_path": path,
            "content": _commit_content(item["content"]),
        }
        # Prefer base64 when present — commit_create text path expands \\n and corrupts .py.
        if item.get("binary") or str(item.get("encoding") or "").lower() == "base64":
            action["encoding"] = "base64"
        actions.append(action)
    return actions


async def _publish_files_via_file_api(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    files: list[dict[str, Any]],
    existing_paths: set[str],
    skip_ci_tracker: "_SkipCiCommitTracker | None" = None,
) -> list[str]:
    """Upload one file per MCP call (required for HTTP MCP behind restrictive WAF)."""
    commit_ids: list[str] = []
    for item in files:
        path = item["path"].lstrip("/")
        tool = "gitlab_file_update" if path in existing_paths else "gitlab_file_create"
        message = _publish_commit_message(slug)
        if skip_ci_tracker is not None:
            message = skip_ci_tracker.message(message)
        payload: dict[str, Any] = {
            "project_id": project_id,
            "file_path": path,
            "branch": branch,
            "commit_message": message,
            "content": item["content"],
        }
        if item.get("binary") or str(item.get("encoding") or "").lower() == "base64":
            payload["encoding"] = "base64"
        result = await call_gitlab_mcp_tool(session, tool, payload)
        existing_paths.add(path)
        commit_id = result.get("id") or result.get("short_id") or result.get("commit_id")
        if commit_id:
            commit_ids.append(str(commit_id))
    return commit_ids


async def _publish_text_file_batches(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    text_files: list[dict[str, Any]],
    existing_paths: set[str],
    skip_ci_tracker: "_SkipCiCommitTracker | None" = None,
) -> list[str]:
    # CloudFront WAF limits POST bodies — one file per MCP call. Direct ALB uses batched commits.
    if use_gitlab_mcp_http() and gitlab_mcp_uses_cloudfront():
        return await _publish_files_via_file_api(
            session,
            project_id=project_id,
            branch=branch,
            slug=slug,
            files=text_files,
            existing_paths=existing_paths,
            skip_ci_tracker=skip_ci_tracker,
        )

    commit_ids: list[str] = []
    batches = _batch_files(text_files)
    for batch in batches:
        message = _publish_commit_message(slug)
        if skip_ci_tracker is not None:
            message = skip_ci_tracker.message(message)
        commit_result = await call_gitlab_mcp_tool(
            session,
            "gitlab_commit_create",
            {
                "project_id": project_id,
                "branch": branch,
                "commit_message": message,
                "actions": _commit_actions(batch, existing_paths),
            },
        )
        for item in batch:
            existing_paths.add(item["path"].lstrip("/"))
        commit_id = commit_result.get("id") or commit_result.get("short_id")
        if commit_id:
            commit_ids.append(str(commit_id))
    return commit_ids


# --- MCP tool actions (projects, branch files, MR notes) ---


async def list_projects_async(
    *,
    project_id: str | None = None,
    membership: bool = True,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List GitLab projects visible to the authenticated user."""
    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()
    async with gitlab_mcp_session() as session:
        data = await call_gitlab_mcp_tool(
            session,
            "gitlab_project_list",
            {
                "membership": membership,
                "page": page,
                "per_page": per_page,
            },
        )
        projects = data.get("projects") or data.get("items") or []
        return {
            "ok": True,
            "projects": projects,
            "pagination": data.get("pagination"),
            "scopeProject": project,
        }


async def list_branch_files_async(
    *,
    branch: str,
    project_id: str | None = None,
    blobs_only: bool = False,
) -> dict[str, Any]:
    """List repository tree entries on a branch (files and folders)."""
    ref = branch.strip()
    if not ref:
        return {"ok": False, "error": "branch is required"}

    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()

    async with gitlab_mcp_session() as session:
        entries = await _list_repository_tree_async(session, project_id=project, ref=ref)
        if blobs_only:
            entries = [entry for entry in entries if entry["type"] == "blob"]
        return {
            "ok": True,
            "project": project,
            "branch": ref,
            "entries": entries,
            "count": len(entries),
        }


async def list_mr_notes_async(
    *,
    mr_iid: int,
    project_id: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    """List top-level notes (comments) on a merge request."""
    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()
    async with gitlab_mcp_session() as session:
        data = await call_gitlab_mcp_tool(
            session,
            "gitlab_mr_notes_list",
            {
                "project_id": project,
                "merge_request_iid": mr_iid,
                "page": page,
                "per_page": per_page,
            },
        )
        notes = data.get("notes") or data.get("items") or []
        return {
            "ok": True,
            "project": project,
            "mrIid": mr_iid,
            "notes": notes,
            "pagination": data.get("pagination"),
        }


async def create_mr_note_async(
    *,
    mr_iid: int,
    body: str,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Add a comment to a merge request."""
    text = body.strip()
    if not text:
        return {"ok": False, "error": "comment body is required"}

    gitlab_personal_access_token()
    project = (project_id or gitlab_project_path()).strip()

    async with gitlab_mcp_session() as session:
        note = await call_gitlab_mcp_tool(
            session,
            "gitlab_mr_note_create",
            {
                "project_id": project,
                "merge_request_iid": mr_iid,
                "body": text,
            },
        )
        return {
            "ok": True,
            "project": project,
            "mrIid": mr_iid,
            "note": note,
        }


def list_projects(**kwargs: Any) -> dict[str, Any]:
    return _run(list_projects_async(**kwargs))


def list_branch_files(**kwargs: Any) -> dict[str, Any]:
    return _run(list_branch_files_async(**kwargs))


def list_mr_notes(**kwargs: Any) -> dict[str, Any]:
    return _run(list_mr_notes_async(**kwargs))


def create_mr_note(**kwargs: Any) -> dict[str, Any]:
    return _run(create_mr_note_async(**kwargs))


# --- SDLC publish workflow ---

def _publish_commit_message(slug: str) -> str:
    return f"feat({slug}): SDLC Agentic AI Pipeline Output"


class _SkipCiCommitTracker:
    """Marks every publish commit except the last with ``[skip ci]``.

    A publish behind CloudFront/WAF pushes one commit per file (see
    ``_publish_batch_size``); each push otherwise triggers its own GitLab
    pipeline on the ``sdlc/<slug>`` branch, racing and auto-cancelling on the
    shared resource_group. Skipping CI for every commit but the true final one
    means GitLab creates exactly one pipeline per publish, for the complete
    file set.
    """

    def __init__(self, total_commits: int) -> None:
        self._remaining = total_commits

    def message(self, base: str) -> str:
        self._remaining -= 1
        if self._remaining > 0:
            return f"{base} [skip ci]"
        return base


async def _publish_binary_files(
    session: Any,
    *,
    project_id: str,
    branch: str,
    slug: str,
    binary_files: list[dict[str, Any]],
    existing_paths: set[str],
    skip_ci_tracker: "_SkipCiCommitTracker | None" = None,
) -> list[str]:
    """jmrplens commit_create schema has no per-action encoding; use file_create/update."""
    return await _publish_files_via_file_api(
        session,
        project_id=project_id,
        branch=branch,
        slug=slug,
        files=binary_files,
        existing_paths=existing_paths,
        skip_ci_tracker=skip_ci_tracker,
    )


async def _ensure_publish_branch(
    session: Any,
    *,
    project_id: str,
    branch: str,
    base_branch: str,
) -> set[str]:
    try:
        await call_gitlab_mcp_tool(
            session,
            "gitlab_branch_get",
            {"project_id": project_id, "branch_name": branch},
        )
    except (GitLabMcpError, BaseExceptionGroup) as exc:
        if not _is_branch_not_found(exc):
            raise
        await call_gitlab_mcp_tool(
            session,
            "gitlab_branch_create",
            {"project_id": project_id, "branch_name": branch, "ref": base_branch},
        )
    return await list_existing_blob_paths(session, project_id=project_id, ref=branch)


def _local_marker_run_id(files: list[dict[str, Any]]) -> str | None:
    """Extract runId from the .sdlc/pipeline-run.json entry about to be published."""
    for item in files:
        if item["path"].endswith(".sdlc/pipeline-run.json") and not item.get("binary"):
            try:
                return str(json.loads(item["content"]).get("runId") or "").strip() or None
            except (ValueError, TypeError):
                return None
    return None


async def _fetch_remote_marker_run_id(
    project_id: str, branch: str, marker_path: str
) -> str | None:
    """Best-effort read of an already-published run marker via the GitLab REST API.

    Used only to detect a duplicate publish invocation for the same run. Any failure
    (network, 404, auth) is treated as "no marker present" so a legitimate publish is
    never blocked by this check — it fails open.
    """
    url = (
        f"{gitlab_api_url()}/projects/{quote(project_id, safe='')}"
        f"/repository/files/{quote(marker_path, safe='')}/raw"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                url,
                params={"ref": branch},
                headers={"PRIVATE-TOKEN": gitlab_personal_access_token()},
            )
        if resp.status_code != 200:
            return None
        return str(json.loads(resp.text).get("runId") or "").strip() or None
    except Exception:  # noqa: BLE001 — fail open, this is a best-effort dedupe check
        return None


async def _publish_already_landed(
    *,
    project_id: str,
    branch: str,
    files: list[dict[str, Any]],
    existing_paths: set[str],
) -> bool:
    """True when this exact run's files are already fully committed on the branch.

    Guards against re-running a full publish (new commits, new CI pipeline) when a
    retry — AgentCore ARN-invoke HTTP fallback (a2a_invoke.py), the frontend's
    SDLC_GITLAB_PUBLISH_RETRIES, or a manual re-run — re-invokes gitlab-agent for a
    publish that already succeeded. runId is a fresh UUID per orchestrator run, so a
    matching runId marker plus a fully-present file set can only mean "this exact
    publish already landed," never a legitimately different publish.
    """
    local_run_id = _local_marker_run_id(files)
    if not local_run_id:
        return False
    marker_item = next(
        (f for f in files if f["path"].endswith(".sdlc/pipeline-run.json")), None
    )
    if marker_item is None or marker_item["path"] not in existing_paths:
        return False
    if not all(f["path"] in existing_paths for f in files):
        return False
    remote_run_id = await _fetch_remote_marker_run_id(
        project_id, branch, marker_item["path"]
    )
    return remote_run_id is not None and remote_run_id == local_run_id


def _publish_error(
    slug: str,
    publish_branch: str,
    cfg: dict[str, str],
    exc: BaseException,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": _mcp_error_message(exc),
        "targetApp": slug,
        "branch": publish_branch,
        "gitlabProject": cfg["project"],
        "gitlabBaseBranch": cfg["base"],
    }


def _is_cloudfront_waf_403(exc: BaseException) -> bool:
    message = _mcp_error_message(exc).lower()
    return "403 forbidden" in message and "cloudfront.net/mcp" in message


def _empty_publish_diagnostic(slug: str, *, root: Path) -> str:
    """Hint why file collection returned nothing (S3 layout vs monorepo layout)."""
    cloud = is_cloud_materialized_workspace(root, slug)
    local_app = (root / "target-apps" / slug).is_dir()
    cloud_app = (root / slug).is_dir()
    entries = len(collect_feature_artifact_entries(slug, root=root))
    parts = [
        f" workspace={root}",
        f"cloud_layout={cloud}",
        f"has_target_apps={local_app}",
        f"has_slug_root={cloud_app}",
        f"mapped_entries={entries}",
    ]
    if cloud_app and not local_app and entries == 0:
        parts.append(
            "hint=cloud S3 tree present but no paths mapped; redeploy gitlab_agent with latest _shared/gitlab_mcp_actions.py"
        )
    elif not cloud_app and not local_app:
        parts.append("hint=materialized workspace empty or wrong runId; check ARTIFACT_STORE=s3 and S3 IAM on runtime")
    return " (" + ", ".join(parts) + ")"


async def publish_feature_async(
    feature: str,
    *,
    project: str | None = None,
    base_branch: str | None = None,
    branch: str | None = None,
    draft_mr: bool = False,
    open_mr: bool = False,
    root: Any | None = None,
    layout: PublishLayout = "monorepo",
) -> dict[str, Any]:
    """Push feature artifacts via jmrplens MCP (gitlab_commit_create); MR is opt-in."""
    gitlab_personal_access_token()
    root_path = root or repo_root()
    slug = slugify_feature(feature)
    cfg = gitlab_repo_config(project=project, base_branch=base_branch)
    if layout == "apps":
        publish_branch = (branch or apps_branch_name(slug)).strip()
        files = _collect_apps_repo_publish_files(slug, root=root_path)
    else:
        publish_branch = (branch or publish_branch_name(slug)).strip()
        files = _collect_monorepo_publish_files(slug, root=root_path)
    project_id = cfg["project"]

    if not files:
        detail = _empty_publish_diagnostic(slug, root=root_path)
        return {
            "ok": False,
            "error": f"No publishable artifacts found for '{slug}'{detail}",
            "targetApp": slug,
            "branch": publish_branch,
            **cfg,
        }

    try:
        assert_publish_python_syntax(files)
    except ValueError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "targetApp": slug,
            "branch": publish_branch,
            **cfg,
        }

    commits: list[str] = []
    project_web_url: str | None = None
    mr_result: dict[str, Any] = {}
    already_published = False

    async def _run_publish(session: Any) -> None:
        nonlocal project_web_url, mr_result, already_published
        project_info = await call_gitlab_mcp_tool(
            session,
            "gitlab_project_get",
            {"project_id": project_id},
        )
        project_web_url = str(project_info.get("web_url") or "").strip() or None

        existing_paths = await _ensure_publish_branch(
            session,
            project_id=project_id,
            branch=publish_branch,
            base_branch=cfg["base"],
        )

        if await _publish_already_landed(
            project_id=project_id,
            branch=publish_branch,
            files=files,
            existing_paths=existing_paths,
        ):
            already_published = True
            print(
                f"[gitlab-mcp] publish for '{slug}' already landed on {publish_branch} "
                "(matching runId marker, all paths present) — skipping duplicate "
                "publish invocation instead of pushing new commits.",
                flush=True,
            )
            return

        text_files, binary_files = _split_publish_files(files)

        if use_gitlab_mcp_http() and gitlab_mcp_uses_cloudfront():
            text_commit_count = len(text_files)
        else:
            text_commit_count = len(_batch_files(text_files)) if text_files else 0
        total_commits = text_commit_count + len(binary_files)
        # Only worth tracking when a publish produces more than one commit —
        # that's the case that would otherwise trigger one GitLab pipeline per commit.
        skip_ci_tracker = _SkipCiCommitTracker(total_commits) if total_commits > 1 else None

        commits.extend(
            await _publish_text_file_batches(
                session,
                project_id=project_id,
                branch=publish_branch,
                slug=slug,
                text_files=text_files,
                existing_paths=existing_paths,
                skip_ci_tracker=skip_ci_tracker,
            )
        )

        commits.extend(
            await _publish_binary_files(
                session,
                project_id=project_id,
                branch=publish_branch,
                slug=slug,
                binary_files=binary_files,
                existing_paths=existing_paths,
                skip_ci_tracker=skip_ci_tracker,
            )
        )

        if open_mr:
            title = f"feat({slug}): SDLC pipeline output"
            if draft_mr:
                title = f"Draft: {title}"
            mr_result = await call_gitlab_mcp_tool(
                session,
                "gitlab_mr_create",
                {
                    "project_id": project_id,
                    "source_branch": publish_branch,
                    "target_branch": cfg["base"],
                    "title": title,
                    "description": _mr_body(slug, [f["path"] for f in files]),
                },
            )

    mcp_urls = gitlab_mcp_publish_url_candidates() if use_gitlab_mcp_http() else []
    attempt_urls: list[str | None] = mcp_urls if mcp_urls else [None]
    last_exc: BaseException | None = None
    publish_started = time.monotonic()

    for index, mcp_url in enumerate(attempt_urls):
        try:
            if mcp_url:
                async with using_gitlab_mcp_url(mcp_url):
                    async with gitlab_mcp_session() as session:
                        await _run_publish(session)
            else:
                async with gitlab_mcp_session() as session:
                    await _run_publish(session)
            break
        except (GitLabMcpError, BaseExceptionGroup) as exc:
            last_exc = exc
            has_fallback = index < len(attempt_urls) - 1
            if not (_is_cloudfront_waf_403(exc) and has_fallback):
                return _publish_error(slug, publish_branch, cfg, exc)
    else:
        if last_exc is not None:
            return _publish_error(slug, publish_branch, cfg, last_exc)
        return _publish_error(slug, publish_branch, cfg, GitLabMcpError("GitLab MCP publish failed"))

    mr_url = str(mr_result.get("web_url") or "")
    branch_url = _branch_tree_url(project_web_url, publish_branch) if project_web_url else None
    elapsed_sec = round(time.monotonic() - publish_started, 2)
    return {
        "ok": True,
        "status": "already-published" if already_published else "published",
        "targetApp": slug,
        "branch": publish_branch,
        "gitlabProject": cfg["project"],
        "gitlabBaseBranch": cfg["base"],
        "publishLayout": layout,
        "openMergeRequest": open_mr,
        "pathsPublished": [f["path"] for f in files],
        "commits": commits,
        "commitCount": len(commits),
        "fileCount": len(files),
        "elapsedSec": elapsed_sec,
        "mcpUrl": attempt_urls[0] if attempt_urls and attempt_urls[0] else None,
        "mergeRequestUrl": mr_url or None,
        "mergeRequestIid": mr_result.get("iid"),
        "repoUrl": project_web_url,
        "branchUrl": branch_url,
        "skippedDuplicatePublish": already_published,
    }


def publish_feature(
    feature: str,
    *,
    project: str | None = None,
    base_branch: str | None = None,
    branch: str | None = None,
    draft_mr: bool = False,
    open_mr: bool = False,
    root: Any | None = None,
    layout: PublishLayout = "monorepo",
) -> dict[str, Any]:
    return _run(
        publish_feature_async(
            feature,
            project=project,
            base_branch=base_branch,
            branch=branch,
            draft_mr=draft_mr,
            open_mr=open_mr,
            root=root,
            layout=layout,
        )
    )
