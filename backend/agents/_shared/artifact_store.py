"""S3 + DynamoDB artifact store with local filesystem fallback."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared.pipeline_context import (
    CANONICAL_RUN_CONTEXT_REL,
    gitlab_handoff_rel_for_app,
    infer_target_app_from_context,
    is_pipeline_context_rel,
    pipeline_context_rel_for_app,
    prd_rel_path_for_app,
    qa_handoff_rel_for_app,
    slugify,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    env_root = os.getenv("REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return _REPO_ROOT


def artifact_store_mode() -> str:
    return os.getenv("ARTIFACT_STORE", "local").strip().lower()


def is_s3_store() -> bool:
    return artifact_store_mode() == "s3"


def s3_bucket() -> str:
    bucket = os.getenv("ARTIFACT_S3_BUCKET", "").strip()
    if not bucket:
        raise ValueError("ARTIFACT_S3_BUCKET is required when ARTIFACT_STORE=s3")
    return bucket


def dynamodb_table_name() -> str:
    return os.getenv("ARTIFACT_DYNAMODB_TABLE", "sdlc-pipeline-runs").strip()


def dynamodb_enabled() -> bool:
    """Run index + artifact pointers in DynamoDB (orchestrator). Off by default for S3-only v1."""
    raw = os.getenv("ARTIFACT_DYNAMODB_ENABLED", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def run_s3_prefix(run_id: str) -> str:
    return f"runs/{run_id.strip()}/"


def new_run_id() -> str:
    return str(uuid.uuid4())


def resolve_run_id(context: dict[str, Any] | None = None) -> str | None:
    if context:
        for key in ("runId", "run_id", "pipelineRunId"):
            value = context.get(key)
            if value and str(value).strip():
                return str(value).strip()
    env_run = os.getenv("PIPELINE_RUN_ID", "").strip()
    return env_run or None


def _local_path(rel_path: str, *, run_id: str | None = None) -> Path:
    rel = rel_path.lstrip("/").replace("\\", "/")
    if run_id:
        return repo_root() / "agents" / "pipeline" / "runs" / run_id / rel
    return repo_root() / rel


def _s3_client() -> Any:
    import boto3

    region = os.getenv("AWS_REGION", "us-east-2")
    return boto3.client("s3", region_name=region)


def _dynamodb_table() -> Any:
    import boto3

    region = os.getenv("AWS_REGION", "us-east-2")
    resource = boto3.resource("dynamodb", region_name=region)
    return resource.Table(dynamodb_table_name())


def put_artifact(
    run_id: str,
    rel_path: str,
    content: str | bytes,
    *,
    content_type: str | None = None,
) -> str:
    """Store artifact bytes; returns stored relative path."""
    rel = rel_path.lstrip("/").replace("\\", "/")
    body = content.encode("utf-8") if isinstance(content, str) else content

    if is_s3_store():
        key = f"{run_s3_prefix(run_id)}{rel}"
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        _s3_client().put_object(Bucket=s3_bucket(), Key=key, Body=body, **extra)
        _put_dynamodb_pointer(run_id, rel, s3_uri=f"s3://{s3_bucket()}/{key}")
        return rel

    dest = _local_path(rel, run_id=run_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return rel


def get_artifact(run_id: str, rel_path: str) -> bytes:
    """Load artifact bytes for a pipeline run."""
    rel = rel_path.lstrip("/").replace("\\", "/")

    if is_s3_store():
        key = f"{run_s3_prefix(run_id)}{rel}"
        response = _s3_client().get_object(Bucket=s3_bucket(), Key=key)
        body = response["Body"].read()
        return body if isinstance(body, bytes) else bytes(body)

    path = _local_path(rel, run_id=run_id)
    if not path.is_file():
        raise FileNotFoundError(f"Artifact not found: {path}")
    return path.read_bytes()


def get_artifact_text(run_id: str, rel_path: str) -> str:
    return get_artifact(run_id, rel_path).decode("utf-8")


def _merge_context_updates(
    existing: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Shallow-merge context updates; incoming non-empty values win."""
    merged = dict(existing)
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        merged[key] = value
    return merged


def put_context(run_id: str, context: dict[str, Any]) -> dict[str, Any]:
    """Persist run-scoped pipeline handoff at runs/<runId>/context.json.

    Merges with any existing context.json so specialist and orchestrator writes
    accumulate rather than overwrite. Returns the merged payload written.
    """
    existing = _load_context_artifact(run_id, CANONICAL_RUN_CONTEXT_REL) or {}
    payload = _merge_context_updates(existing, context)
    payload["runId"] = run_id
    put_artifact(
        run_id,
        CANONICAL_RUN_CONTEXT_REL,
        json.dumps(payload, indent=2) + "\n",
        content_type="application/json",
    )
    return payload


def run_artifact_exists(run_id: str, rel_path: str) -> bool:
    """True when runs/<runId>/<rel_path> exists in the artifact store."""
    rel = rel_path.lstrip("/").replace("\\", "/")
    try:
        get_artifact(run_id, rel)
    except FileNotFoundError:
        return False
    return True


def enrich_db_paths_from_run(ctx: dict[str, Any]) -> dict[str, Any]:
    """Fill db/sql handoff paths from run store when local disk is unavailable (cloud)."""
    run_id = resolve_run_id(ctx)
    app = infer_target_app_from_context(ctx)
    if not run_id or not app:
        return ctx

    slug = slugify(app)
    db_dir = f"target-apps/{slug}/db"
    sql_dir = f"{db_dir}/sql"
    ctx.setdefault("dbOutputDir", db_dir)
    ctx.setdefault("preferredSqlPath", sql_dir)
    ctx.setdefault("preferredNoSqlPath", f"{db_dir}/nosql")

    if run_sql_artifact_keys(run_id, slug):
        ctx["dbOutputDir"] = db_dir
        ctx["preferredSqlPath"] = sql_dir

    handoff_rel = f"{db_dir}/HANDOFF.md"
    if run_artifact_exists(run_id, handoff_rel):
        ctx["databaseHandoffPath"] = handoff_rel

    return ctx


def _load_context_artifact(run_id: str, rel_path: str) -> dict[str, Any] | None:
    try:
        raw = get_artifact_text(run_id, rel_path)
    except FileNotFoundError:
        return None
    except Exception as exc:
        if is_s3_store():
            from botocore.exceptions import ClientError

            if isinstance(exc, ClientError) and exc.response["Error"]["Code"] == "NoSuchKey":
                return None
        raise
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed.setdefault("runId", run_id)
        return parsed
    return None


def get_context(run_id: str, *, target_app: str | None = None) -> dict[str, Any] | None:
    """Load pipeline context for a run (canonical context.json, legacy per-app fallback)."""
    loaded = _load_context_artifact(run_id, CANONICAL_RUN_CONTEXT_REL)
    if loaded:
        return loaded

    if target_app:
        legacy = pipeline_context_rel_for_app(target_app)
        return _load_context_artifact(run_id, legacy)

    return None


def register_pipeline_run(run_id: str, target_app: str, *, status: str = "running") -> None:
    """Orchestrator-only: create DynamoDB run index row (META)."""
    if not is_s3_store() or not dynamodb_enabled():
        return
    now = datetime.now(UTC).isoformat()
    _dynamodb_table().put_item(
        Item={
            "runId": run_id,
            "artifactKey": "META",
            "targetApp": target_app,
            "status": status,
            "createdAt": now,
            "updatedAt": now,
            "contextS3Key": f"{run_s3_prefix(run_id)}context.json",
        }
    )


def update_pipeline_run(
    run_id: str,
    *,
    status: str | None = None,
    last_agent: str | None = None,
) -> None:
    """Orchestrator-only: update DynamoDB run index after a pipeline step."""
    if not is_s3_store() or not dynamodb_enabled():
        return
    now = datetime.now(UTC).isoformat()
    expr_names: dict[str, str] = {"#u": "updatedAt"}
    expr_values: dict[str, Any] = {":u": now}
    set_parts = ["#u = :u"]
    if status:
        expr_names["#s"] = "status"
        expr_values[":s"] = status
        set_parts.append("#s = :s")
    if last_agent:
        expr_names["#a"] = "lastAgent"
        expr_values[":a"] = last_agent
        set_parts.append("#a = :a")
    _dynamodb_table().update_item(
        Key={"runId": run_id, "artifactKey": "META"},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def sync_repo_paths_to_run(run_id: str, rel_paths: list[str]) -> list[str]:
    """Upload repo-relative files (or trees) into runs/<runId>/ on S3/local."""
    root = repo_root()
    synced: list[str] = []
    seen: set[str] = set()
    for rel in rel_paths:
        normalized = rel.lstrip("/").replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        src = root / normalized
        if src.is_file():
            put_artifact(run_id, normalized, src.read_bytes())
            synced.append(normalized)
            seen.add(normalized)
        elif src.is_dir():
            for file_path in src.rglob("*"):
                if not file_path.is_file():
                    continue
                file_rel = file_path.relative_to(root).as_posix()
                if file_rel in seen:
                    continue
                put_artifact(run_id, file_rel, file_path.read_bytes())
                synced.append(file_rel)
                seen.add(file_rel)
    return synced


def artifact_paths_for_agent(agent_name: str, feature: str, context: dict[str, Any]) -> list[str]:
    """Repo paths each specialist agent produces (diagram: agents -> S3)."""
    slug = feature
    paths: list[str] = []
    if agent_name == "product-agent":
        prd = context.get("prdPath") or prd_rel_path_for_app(slug)
        paths.append(str(prd))
        paths.append(pipeline_context_rel_for_app(slug))
        input_path = context.get("inputPath") or context.get("inputFile")
        if input_path:
            paths.append(str(input_path).replace("\\", "/"))
    elif agent_name == "architect-agent":
        from _shared.pipeline_context import design_doc_rel_for_app, diagram_path_for_app

        paths.append(str(context.get("designDocPath") or design_doc_rel_for_app(slug)))
        for diagram in context.get("diagramPaths") or [diagram_path_for_app(slug)]:
            paths.append(str(diagram))
    elif agent_name == "database-agent":
        paths.append(f"target-apps/{slug}/db")
    elif agent_name == "developer-agent":
        paths.append(f"target-apps/{slug}")
    elif agent_name == "gitlab-agent":
        paths.append(gitlab_handoff_rel_for_app(slug))
    elif agent_name == "qa-agent":
        paths.append(qa_handoff_rel_for_app(slug))
    return paths


def run_sql_artifact_keys(run_id: str, feature: str) -> list[str]:
    """List `.sql` migration paths for a feature under runs/<runId>/target-apps/<feature>/db/sql/."""
    prefix = f"target-apps/{feature.strip()}/db/sql/"
    return [
        key
        for key in list_run_artifact_keys(run_id)
        if key.startswith(prefix) and key.lower().endswith(".sql")
    ]


def list_run_artifact_keys(run_id: str) -> list[str]:
    """List relative artifact paths under a run prefix."""
    if is_s3_store():
        prefix = run_s3_prefix(run_id)
        client = _s3_client()
        keys: list[str] = []
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": s3_bucket(), "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = client.list_objects_v2(**kwargs)
            for item in page.get("Contents") or []:
                key = str(item.get("Key") or "")
                if key.startswith(prefix):
                    keys.append(key[len(prefix) :])
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
        return sorted(keys)

    base = repo_root() / "agents" / "pipeline" / "runs" / run_id
    if not base.is_dir():
        return []
    return sorted(
        p.relative_to(base).as_posix()
        for p in base.rglob("*")
        if p.is_file()
    )


def materialize_run(run_id: str, dest: Path | None = None) -> Path:
    """Download run artifacts into a workspace directory."""
    workspace = dest or Path(tempfile.mkdtemp(prefix=f"sdlc-run-{run_id[:8]}-"))
    workspace.mkdir(parents=True, exist_ok=True)

    for rel in list_run_artifact_keys(run_id):
        if not rel or rel.endswith("/"):
            continue
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(get_artifact(run_id, rel))
    return workspace


def write_repo_artifact(
    rel_path: str,
    content: str | bytes,
    *,
    context: dict[str, Any] | None = None,
) -> str:
    """Write to local repo path or run artifact store when runId is present."""
    run_id = resolve_run_id(context)
    rel = rel_path.lstrip("/").replace("\\", "/")
    if run_id and is_pipeline_context_rel(rel):
        # Canonical run handoff is context.json (put_context); skip duplicate per-app copy.
        return rel_path
    if run_id:
        return put_artifact(run_id, rel_path, content)
    dest = repo_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        dest.write_text(content, encoding="utf-8")
    else:
        dest.write_bytes(content)
    return rel_path


def read_repo_artifact(rel_path: str, *, context: dict[str, Any] | None = None) -> bytes:
    """Read from local repo or run artifact store when runId is present."""
    run_id = resolve_run_id(context)
    rel = rel_path.lstrip("/").replace("\\", "/")
    if run_id and is_pipeline_context_rel(rel):
        return get_artifact(run_id, CANONICAL_RUN_CONTEXT_REL)
    if run_id:
        return get_artifact(run_id, rel)
    path = repo_root() / rel
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return path.read_bytes()


def _put_dynamodb_pointer(
    run_id: str,
    artifact_key: str,
    *,
    s3_uri: str | None = None,
    target_app: str | None = None,
    context_s3_key: str | None = None,
) -> None:
    if not is_s3_store() or not dynamodb_enabled():
        return
    now = datetime.now(UTC).isoformat()
    item: dict[str, Any] = {
        "runId": run_id,
        "artifactKey": artifact_key,
        "updatedAt": now,
    }
    if s3_uri:
        item["s3Uri"] = s3_uri
    if target_app:
        item["targetApp"] = target_app
    if context_s3_key:
        item["contextS3Key"] = context_s3_key
        item["createdAt"] = now
    _dynamodb_table().put_item(Item=item)


def put_handoff(run_id: str, name: str, handoff: dict[str, Any]) -> str:
    """Store handoff JSON under handoffs/<name>.json."""
    rel = f"handoffs/{name}.json"
    put_artifact(run_id, rel, json.dumps(handoff, indent=2) + "\n", content_type="application/json")
    _put_dynamodb_pointer(run_id, f"HANDOFF#{name}", s3_uri=f"s3://{s3_bucket()}/{run_s3_prefix(run_id)}{rel}")
    return rel
