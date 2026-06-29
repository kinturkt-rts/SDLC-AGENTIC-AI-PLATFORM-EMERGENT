"""S3 + DynamoDB artifact store with local filesystem fallback."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _shared.pipeline_context import pipeline_context_rel_for_app, prd_rel_path_for_app

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


def put_context(run_id: str, context: dict[str, Any]) -> None:
    """Persist pipeline context JSON to S3/local artifact store (not DynamoDB)."""
    payload = dict(context)
    payload["runId"] = run_id
    put_artifact(
        run_id,
        "context.json",
        json.dumps(payload, indent=2) + "\n",
        content_type="application/json",
    )


def register_pipeline_run(run_id: str, target_app: str, *, status: str = "running") -> None:
    """Orchestrator-only: create DynamoDB run index row (META)."""
    if not is_s3_store():
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
    if not is_s3_store():
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
        paths.append(str(context.get("designDocPath") or f"docs/design/{slug}.md"))
        for diagram in context.get("diagramPaths") or [f"docs/diagrams/generated-diagrams/{slug}.png"]:
            paths.append(str(diagram))
    elif agent_name == "database-agent":
        paths.append(f"target-apps/{slug}/db")
    elif agent_name == "developer-agent":
        paths.append(f"target-apps/{slug}")
    elif agent_name == "gitlab-agent":
        paths.append(f"agents/pipeline/{slug}.gitlab-handoff.json")
    elif agent_name == "qa-agent":
        paths.append(f"agents/pipeline/{slug}.qa-handoff.json")
    return paths


def get_context(run_id: str) -> dict[str, Any] | None:
    """Load pipeline context for a run."""
    try:
        raw = get_artifact_text(run_id, "context.json")
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
    """Download run artifacts into a workspace directory (repo layout)."""
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
    """Write under runs/<runId>/ when runId is set; else repo-relative path."""
    run_id = resolve_run_id(context)
    if run_id:
        return put_artifact(run_id, rel_path, content)
    dest = repo_root() / rel_path.lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        dest.write_text(content, encoding="utf-8")
    else:
        dest.write_bytes(content)
    return rel_path


def read_repo_artifact(rel_path: str, *, context: dict[str, Any] | None = None) -> bytes:
    """Read from runs/<runId>/ when runId is set; else repo-relative path."""
    run_id = resolve_run_id(context)
    if run_id:
        return get_artifact(run_id, rel_path)
    path = repo_root() / rel_path.lstrip("/")
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
    if not is_s3_store():
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
