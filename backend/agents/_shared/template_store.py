"""Template store for developer-agent scaffolding.

Resolves the path to the golden ``_template/`` scaffold directory.

Lookup order (first match wins):
  1. ``SDLC_TEMPLATE_DIR`` env — explicit override (dev/testing).
  2. Local repo ``backend/target-apps/_template/`` — unchanged local flow.
  3. S3 tarball at ``s3://<bucket>/templates/<version>/template.tar.gz``
     downloaded and extracted to a cache dir under the system temp directory.

Env vars:
  - ``SDLC_TEMPLATE_DIR``: absolute path override (skips S3 entirely).
  - ``SDLC_TEMPLATE_VERSION``: default ``v1.0.0``.
  - ``SDLC_TEMPLATE_S3_BUCKET``: default falls back to ``ARTIFACT_S3_BUCKET``.
  - ``AWS_REGION``: default ``us-east-2``.

Cache: ``<tempdir>/sdlc-templates/<version>/template/`` — reused across warm
container invocations; refreshed only when the version marker changes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_VERSION = "v1.0.0"
_CACHE_ROOT_NAME = "sdlc-templates"


def _repo_template_dir() -> Path:
    """Local ``backend/target-apps/_template/`` path — used when it exists on disk."""
    return Path(__file__).resolve().parents[2] / "target-apps" / "_template"


def _cache_root() -> Path:
    return Path(tempfile.gettempdir()) / _CACHE_ROOT_NAME


def template_version() -> str:
    return os.getenv("SDLC_TEMPLATE_VERSION", DEFAULT_VERSION).strip() or DEFAULT_VERSION


def _template_bucket() -> str:
    bucket = os.getenv("SDLC_TEMPLATE_S3_BUCKET", "").strip()
    if bucket:
        return bucket
    bucket = os.getenv("ARTIFACT_S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError(
            "template store requires SDLC_TEMPLATE_S3_BUCKET or ARTIFACT_S3_BUCKET"
        )
    return bucket


def _s3_client() -> Any:
    import boto3

    region = os.getenv("AWS_REGION", "us-east-2")
    return boto3.client("s3", region_name=region)


def _manifest_key(version: str) -> str:
    return f"templates/{version}/manifest.json"


def _template_key(version: str) -> str:
    return f"templates/{version}/template.tar.gz"


def _download_bytes(bucket: str, key: str) -> bytes:
    client = _s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()
    return body if isinstance(body, bytes) else bytes(body)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_manifest(bucket: str, version: str) -> dict[str, Any]:
    try:
        raw = _download_bytes(bucket, _manifest_key(version))
    except Exception as exc:
        logger.warning("template manifest fetch failed (version=%s): %s", version, exc)
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _extract_tarball(archive_bytes: bytes, dest: Path) -> Path:
    """Extract ``template.tar.gz`` into ``dest`` and return the ``template/`` subdir."""
    dest.mkdir(parents=True, exist_ok=True)
    tarball_path = dest / "template.tar.gz"
    tarball_path.write_bytes(archive_bytes)
    with tarfile.open(tarball_path, "r:gz") as tf:
        for member in tf.getmembers():
            name = member.name.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise RuntimeError(f"unsafe tarball member: {member.name}")
        tf.extractall(dest)  # noqa: S202 - members validated above
    tarball_path.unlink(missing_ok=True)
    template_dir = dest / "template"
    if not (template_dir / "scaffold-manifest.json").is_file():
        raise RuntimeError(
            f"template tarball missing template/scaffold-manifest.json under {dest}"
        )
    return template_dir


def _cache_dir_for_version(version: str) -> Path:
    return _cache_root() / version


def _is_cache_valid(cache_dir: Path, expected_sha: str | None) -> bool:
    marker = cache_dir / ".version"
    template_dir = cache_dir / "template"
    if not (template_dir / "scaffold-manifest.json").is_file():
        return False
    if not marker.is_file():
        return False
    if not expected_sha:
        return True
    try:
        return marker.read_text(encoding="utf-8").strip() == expected_sha
    except OSError:
        return False


def _fetch_and_extract(version: str) -> Path:
    bucket = _template_bucket()
    manifest = _load_manifest(bucket, version)
    expected_sha = str(manifest.get("templateSha256", "")).strip() or None

    cache_dir = _cache_dir_for_version(version)
    if _is_cache_valid(cache_dir, expected_sha):
        logger.info("template cache hit: version=%s dir=%s", version, cache_dir)
        return cache_dir / "template"

    logger.info(
        "downloading template from s3://%s/%s (version=%s)",
        bucket,
        _template_key(version),
        version,
    )
    archive = _download_bytes(bucket, _template_key(version))
    actual_sha = _sha256(archive)
    if expected_sha and actual_sha != expected_sha:
        raise RuntimeError(
            f"template.tar.gz sha256 mismatch for {version}: "
            f"expected {expected_sha}, got {actual_sha}"
        )

    if cache_dir.exists():
        for child in cache_dir.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    template_dir = _extract_tarball(archive, cache_dir)
    (cache_dir / ".version").write_text(actual_sha, encoding="utf-8")
    logger.info(
        "extracted template version=%s files=%d dir=%s",
        version,
        sum(1 for _ in template_dir.rglob("*") if _.is_file()),
        template_dir,
    )
    return template_dir


_resolved_dir: Path | None = None


def get_template_dir() -> Path:
    """Return the path to the scaffold template directory (memoized)."""
    global _resolved_dir
    if _resolved_dir is not None and (_resolved_dir / "scaffold-manifest.json").is_file():
        return _resolved_dir

    override = os.getenv("SDLC_TEMPLATE_DIR", "").strip()
    if override:
        path = Path(override).expanduser().resolve()
        if not (path / "scaffold-manifest.json").is_file():
            raise RuntimeError(
                f"SDLC_TEMPLATE_DIR={path} missing scaffold-manifest.json"
            )
        _resolved_dir = path
        return path

    local = _repo_template_dir()
    if (local / "scaffold-manifest.json").is_file():
        _resolved_dir = local
        return local

    version = template_version()
    _resolved_dir = _fetch_and_extract(version)
    return _resolved_dir


def reset_cache() -> None:
    """Testing hook — forget the memoized resolution."""
    global _resolved_dir
    _resolved_dir = None
