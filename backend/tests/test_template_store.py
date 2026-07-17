"""Tests for template_store S3 extraction (developer-agent cloud scaffolding).

Regression coverage for the folder-name mismatch bug: publish-template-to-s3.py
archives the source directory verbatim as "_template/...", but _extract_tarball
previously looked for "template/..." after extraction - get_template_dir() always
raised on cloud runtimes, silently swallowed by developer_agent's broad except,
falling back to a local path that doesn't exist in the container. Net effect:
dev_scaffold never had real template files to copy on AgentCore, every "golden"
file had to be hand-written by the LLM, and the final structure-validation gate
failed for files the LLM skipped or got wrong (app/database.py, startup_checks.py,
routers/health.py) - this was masked for a long time because cloud developer-agent
invocations used to be killed by the AgentCore 15-minute sync cap before ever
reaching that final validation gate.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared import template_store  # noqa: E402


def _build_fake_template_tarball(dest: Path) -> bytes:
    """Mirror publish-template-to-s3.py: archive preserves the "_template" folder name."""
    src_root = dest / "_template"
    (src_root / "app").mkdir(parents=True)
    (src_root / "scaffold-manifest.json").write_text("{}", encoding="utf-8")
    (src_root / "app" / "database.py").write_text("# db", encoding="utf-8")

    archive_path = dest / "template.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        for path in sorted(src_root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(dest)
                tf.add(path, arcname=rel.as_posix())
    return archive_path.read_bytes()


def test_extract_tarball_resolves_underscore_template_dir(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    archive_bytes = _build_fake_template_tarball(build_dir)

    extract_dest = tmp_path / "extracted"
    template_dir = template_store._extract_tarball(archive_bytes, extract_dest)

    assert template_dir == extract_dest / "_template"
    assert (template_dir / "scaffold-manifest.json").is_file()
    assert (template_dir / "app" / "database.py").is_file()


def test_extract_tarball_raises_when_manifest_missing(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    (build_dir / "_template").mkdir(parents=True)
    (build_dir / "_template" / "app.py").write_text("x", encoding="utf-8")
    archive_path = build_dir / "template.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(build_dir / "_template" / "app.py", arcname="_template/app.py")
    archive_bytes = archive_path.read_bytes()

    with pytest.raises(RuntimeError, match="scaffold-manifest.json"):
        template_store._extract_tarball(archive_bytes, tmp_path / "extracted2")


def test_is_cache_valid_checks_underscore_template_dir(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache" / "v1.0.0"
    template_dir = cache_dir / "_template"
    template_dir.mkdir(parents=True)
    (template_dir / "scaffold-manifest.json").write_text("{}", encoding="utf-8")
    (cache_dir / ".version").write_text("abc123", encoding="utf-8")

    assert template_store._is_cache_valid(cache_dir, "abc123") is True
    assert template_store._is_cache_valid(cache_dir, "different-sha") is False