"""Golden-template scaffolding for developer-agent — deterministic file copies."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

_VALID_PATTERNS = ("B", "B-api-key", "B+", "B++", "F", "F-api-key")


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise FileNotFoundError(f"scaffold manifest not found: {manifest_path}")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "patterns" not in data:
        raise ValueError("scaffold manifest must contain a patterns object")
    return data


def resolve_pattern_spec(manifest: dict[str, Any], pattern: str) -> dict[str, Any]:
    """Merge copy_verbatim and copy_as for pattern + extends chain."""
    key = pattern.strip()
    if key not in _VALID_PATTERNS:
        raise ValueError(
            f"unsupported pattern {pattern!r}; use one of: {', '.join(_VALID_PATTERNS)}"
        )

    patterns: dict[str, Any] = manifest["patterns"]
    if key not in patterns:
        raise ValueError(f"pattern {key!r} not defined in scaffold manifest")

    verbatim: list[str] = []
    copy_as: dict[str, str] = {}
    seed_from_template: list[str] = []
    seen: set[str] = set()

    def _merge(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        spec = patterns[name]
        parent = spec.get("extends")
        if parent:
            _merge(str(parent))
        for rel in spec.get("copy_verbatim", []):
            if rel not in verbatim:
                verbatim.append(rel)
        for src, dest in spec.get("copy_as", {}).items():
            copy_as[src] = dest
        for rel in spec.get("seed_from_template", []):
            if rel not in seed_from_template:
                seed_from_template.append(rel)

    _merge(key)
    return {
        "copy_verbatim": verbatim,
        "copy_as": copy_as,
        "seed_from_template": seed_from_template,
        "pattern": key,
    }


def scaffold_service(
    *,
    template_dir: Path,
    service_dir: Path,
    pattern: str,
    force: bool = False,
) -> dict[str, Any]:
    """Copy golden template files into target-apps/<service>/.

    copy_verbatim / copy_as destinations NOT listed in customize_after_scaffold
    always refresh from _template/, even if the destination already exists —
    so regenerating an app never leaves a stale protected file (security.py,
    dependencies.py, routers/auth.py, schemas/auth.py, etc.) in place.
    customize_after_scaffold destinations (app-specific config.py, main.py,
    .env.example, README.md, requirements.txt, tests/conftest.py, ...) are left
    untouched unless force=True, which overwrites everything in the manifest.
    """
    manifest_path = template_dir / "scaffold-manifest.json"
    manifest = load_manifest(manifest_path)
    spec = resolve_pattern_spec(manifest, pattern)

    customize: set[str] = set(manifest.get("customize_after_scaffold", []))
    seed_files = set(spec["seed_from_template"])

    # Protected destinations that refresh every run regardless of `force`.
    # developer_agent.py's _VERBATIM_SCAFFOLD_SUFFIXES (~line 1263) is a hand-maintained
    # subset of this set, used to hard-block LLM writes (not just force-copy). Any new
    # copy_verbatim/copy_as file that should also be hard-blocked from LLM writes needs
    # a matching entry added there. Covered by
    # tests/test_developer_agent.py::test_verbatim_scaffold_suffixes_is_subset_of_manifest_force_refresh.
    always_refresh: set[str] = (
        set(spec["copy_verbatim"]) | set(spec["copy_as"].values())
    ) - customize

    service_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    def _copy_file(src_rel: str, dest_rel: str) -> None:
        src = template_dir / src_rel
        dest = service_dir / dest_rel
        if not src.is_file():
            missing.append(src_rel)
            return
        if dest.is_file() and not (force or dest_rel in always_refresh):
            skipped.append(dest_rel)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(dest_rel)

    for rel in spec["copy_verbatim"]:
        _copy_file(rel, rel)

    for src_rel, dest_rel in spec["copy_as"].items():
        _copy_file(src_rel, dest_rel)

    customize_next = sorted(
        p for p in customize if (service_dir / p).is_file()
    )

    return {
        "pattern": spec["pattern"],
        "copied": copied,
        "skipped": skipped,
        "missing": missing,
        "customize_next": customize_next,
        "seed_files": sorted(seed_files),
        "service_dir": service_dir.as_posix(),
    }


def format_scaffold_report(result: dict[str, Any], *, service: str) -> str:
    """Human-readable report for dev_scaffold tool output."""
    if result["missing"]:
        lines = [
            f"SCAFFOLD FAILED pattern={result['pattern']} service={service}",
            "MISSING template files (fix _template/ or scaffold-manifest.json):",
        ]
        for rel in result["missing"]:
            lines.append(f"  ! {rel}")
        return "\n".join(lines)

    prefix = f"target-apps/{service}/"
    lines = [
        f"SCAFFOLD OK pattern={result['pattern']} service={service}",
        f"Copied {len(result['copied'])} file(s):",
    ]
    for rel in result["copied"]:
        lines.append(f"  + {prefix}{rel}")
    if result["skipped"]:
        lines.append(f"Skipped {len(result['skipped'])} existing file(s) (force=true to overwrite):")
        for rel in result["skipped"]:
            lines.append(f"  ~ {prefix}{rel}")
    lines.append("")
    lines.append("Customize next (dev_write_file after reading design + HANDOFF):")
    for rel in result["customize_next"]:
        note = " (seed — adapt service_name, routers, schema, env vars)" if rel in result["seed_files"] else ""
        lines.append(f"  * {prefix}{rel}{note}")
    lines.append("")
    lines.append(
        "Then GENERATE domain code only: app/models/<entity>.py, app/routers/<domain>.py, "
        "schemas/<domain>.py, app/services/prompts.py (B+), tests/test_<domain>.py, README.md"
    )
    return "\n".join(lines)
