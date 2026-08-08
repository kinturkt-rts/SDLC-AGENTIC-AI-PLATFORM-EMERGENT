"""Publish target-apps/_template to S3 for AgentCore developer-agent scaffolding"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE_DIR = _REPO_ROOT / "target-apps" / "_template"
_DEFAULT_VERSION = "v1.0.0"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _build_tarball(template_dir: Path) -> bytes:
    if not (template_dir / "scaffold-manifest.json").is_file():
        raise FileNotFoundError(f"Missing scaffold-manifest.json under {template_dir}")

    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / "template.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tf:
            for path in sorted(template_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(template_dir.parent)
                tf.add(path, arcname=rel.as_posix())
        return archive_path.read_bytes()


def publish(*, version: str, bucket: str, region: str) -> dict[str, str]:
    import boto3

    archive = _build_tarball(_TEMPLATE_DIR)
    digest = _sha256_bytes(archive)
    prefix = f"templates/{version}"
    template_key = f"{prefix}/template.tar.gz"
    manifest_key = f"{prefix}/manifest.json"
    manifest = {
        "version": version,
        "templateSha256": digest,
        "publishedAt": datetime.now(timezone.utc).isoformat(),
        "source": "target-apps/_template",
    }

    client = boto3.client("s3", region_name=region)
    client.put_object(
        Bucket=bucket,
        Key=template_key,
        Body=archive,
        ContentType="application/gzip",
    )
    client.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return {
        "bucket": bucket,
        "version": version,
        "templateKey": template_key,
        "manifestKey": manifest_key,
        "templateSha256": digest,
        "bytes": str(len(archive)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish _template scaffold to S3")
    parser.add_argument("--version", default=os.getenv("SDLC_TEMPLATE_VERSION", _DEFAULT_VERSION))
    parser.add_argument("--bucket", default=os.getenv("SDLC_TEMPLATE_S3_BUCKET") or os.getenv("ARTIFACT_S3_BUCKET"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-2"))
    args = parser.parse_args()

    if not args.bucket:
        print("ERROR: set ARTIFACT_S3_BUCKET or SDLC_TEMPLATE_S3_BUCKET", file=sys.stderr)
        return 1

    result = publish(version=args.version.strip(), bucket=args.bucket.strip(), region=args.region.strip())
    print(
        f"Published template {result['version']} "
        f"to s3://{result['bucket']}/{result['templateKey']} "
        f"(sha256={result['templateSha256'][:12]}…, {result['bytes']} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())