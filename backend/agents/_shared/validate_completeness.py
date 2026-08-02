"""PART 4b — non-blocking completeness check: built app vs design doc.

This is deliberately WARN-only and additive. `check_design_routes_implemented`
(validate_ui_parity.py) already blocks on missing §4 routes, but its row regex
requires backtick-quoted paths (`` `/api/v1/x` ``) and architect-agent's real
output writes plain paths (`| POST | /api/v1/x | ... |`, no backticks) — so on
real design docs that blocking check silently parses zero rows and never fires.
Entities (§3) and named business rules (§5) have no existing gate at all (see the
prior diagnostic investigation on this repo). This module fills both gaps as
warnings a human can act on, without ever failing a run — a WARN here must never
become a FAIL for anyone relying on this module.
"""

from __future__ import annotations

import re
from pathlib import Path

from _shared.api_surface import collect_implemented_routes, design_doc_for_app, paths_match

_SECTION_HEADER_RE = re.compile(r"^##\s*\d+\.", re.MULTILINE)
_DATA_MODEL_HEADER = re.compile(r"^##\s*3\.\s*Data\s+model\s*$", re.MULTILINE | re.IGNORECASE)
_ROUTES_HEADER = re.compile(r"^##\s*4\.\s*API\s+surface\s*$", re.MULTILINE | re.IGNORECASE)
_RULES_HEADER = re.compile(r"^##\s*5\.\s*Rules\s*$", re.MULTILINE | re.IGNORECASE)

# Lenient route row: backticks around the path are optional (unlike
# api_surface.py's `_DESIGN_ROW`, which requires them and misses real docs).
_ROUTE_ROW = re.compile(
    r"^\|\s*(GET|POST|PATCH|PUT|DELETE)\s*\|\s*`?([^`|]+?)`?\s*\|",
    re.IGNORECASE,
)

_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "for", "with", "on", "in", "per", "all", "per"}


def _section_text(design_text: str, header_re: re.Pattern[str]) -> str:
    match = header_re.search(design_text)
    if not match:
        return ""
    rest = design_text[match.end() :]
    nxt = _SECTION_HEADER_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def parse_design_entities(design_text: str) -> list[str]:
    """Entity/table names from design §3 Data model table (first column)."""
    section = _section_text(design_text, _DATA_MODEL_HEADER)
    if not section:
        return []
    entities: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        name = cells[0]
        low = name.lower()
        if low.startswith("table") or low.startswith("entity") or low.startswith("collection"):
            continue  # header row
        if set(name) <= {"-", ":"}:
            continue  # markdown separator row
        entities.append(name)
    return entities


def parse_design_routes_lenient(design_text: str) -> list[tuple[str, str]]:
    """§4 API surface rows — backticks around the path are optional."""
    section = _section_text(design_text, _ROUTES_HEADER)
    if not section:
        return []
    routes: list[tuple[str, str]] = []
    for line in section.splitlines():
        m = _ROUTE_ROW.match(line.strip())
        if not m:
            continue
        path = m.group(2).strip()
        if not path.startswith("/"):
            continue
        routes.append((m.group(1).upper(), path))
    return routes


def parse_design_rule_names(design_text: str) -> list[str]:
    """Short rule names from §5 Rules bullets, e.g. 'Vehicle capacity (FR-3, FR-5): ...'
    -> 'Vehicle capacity'. Falls back to text before the first ':' when there's no
    parenthetical."""
    section = _section_text(design_text, _RULES_HEADER)
    if not section:
        return []
    names: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        body = stripped.lstrip("-").strip()
        if not body:
            continue
        paren = re.match(r"^([A-Za-z][A-Za-z0-9 /_-]*?)\s*\(", body)
        name = paren.group(1).strip() if paren else body.split(":")[0].strip()
        if name:
            names.append(name)
    return names


def _built_table_names(app_dir: Path) -> set[str]:
    from _shared.validate_sql_artifacts import parse_schema_nullability

    sql_dir = app_dir / "db" / "sql"
    if not sql_dir.is_dir():
        return set()
    nullability = parse_schema_nullability(sql_dir)
    return {table.lower() for _schema, table, _col in nullability}


def _app_source_corpus(app_dir: Path) -> str:
    parts: list[str] = []
    for sub in ("app", "ui", "schemas"):
        directory = app_dir / sub
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.py"):
            try:
                parts.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return "\n".join(parts)


def _find_unimplemented_rule_names(design_text: str, app_dir: Path) -> list[str]:
    """Best-effort only: a rule name whose significant words (>=4 chars) appear
    NOWHERE in app/ui/schemas source is flagged. Lenient by design (ANY token
    match clears the rule) to keep false positives low — this is a heuristic
    hint for a human to check, not a precise implementation-coverage check."""
    names = parse_design_rule_names(design_text)
    if not names:
        return []
    corpus = _app_source_corpus(app_dir).lower()
    if not corpus:
        return []
    gaps: list[str] = []
    for name in names:
        tokens = [
            t.lower()
            for t in re.findall(r"[A-Za-z]{4,}", name)
            if t.lower() not in _STOPWORDS
        ]
        if not tokens:
            continue
        if not any(tok in corpus for tok in tokens):
            gaps.append(name)
    return gaps


def check_completeness_against_design(app_dir: Path, repo_root: Path) -> list[str]:
    """Compare the built app against its design doc; return WARN-only messages.

    Never raises and never signals failure — callers should treat every string
    returned here as a warning, not a blocking error. Each message is prefixed
    with 'COMPLETENESS WARNING:' so it's easy to spot in a validation report.
    """
    try:
        app_slug = app_dir.name
        design_path = design_doc_for_app(app_slug, repo_root)
        if not design_path:
            return []
        design_text = design_path.read_text(encoding="utf-8", errors="replace")

        warnings: list[str] = []

        design_entities = parse_design_entities(design_text)
        if design_entities:
            built_tables = _built_table_names(app_dir)
            missing_entities = [
                e for e in design_entities if e.strip().lower() not in built_tables
            ]
            if missing_entities:
                warnings.append(
                    "COMPLETENESS WARNING: design §3 lists "
                    f"{len(missing_entities)} entit"
                    f"{'y' if len(missing_entities) == 1 else 'ies'} with no matching table "
                    f"in db/sql/ — {', '.join(missing_entities)}"
                )

        design_routes = parse_design_routes_lenient(design_text)
        if design_routes:
            implemented = collect_implemented_routes(app_dir)
            missing_routes = [
                f"{method} {path}"
                for method, path in design_routes
                if not any(
                    im == method and paths_match(path, ip) for im, ip in implemented
                )
            ]
            if missing_routes:
                warnings.append(
                    "COMPLETENESS WARNING: design §4 lists "
                    f"{len(missing_routes)} route(s) with no matching implementation — "
                    f"{', '.join(missing_routes)}"
                )

        rule_gaps = _find_unimplemented_rule_names(design_text, app_dir)
        if rule_gaps:
            warnings.append(
                "COMPLETENESS WARNING: design §5 names "
                f"{len(rule_gaps)} rule(s) with no obvious matching code (best-effort "
                "keyword check — verify manually before treating as a real gap) — "
                + ", ".join(rule_gaps)
            )

        return warnings
    except Exception as exc:  # noqa: BLE001 - this check must never break a run
        return [
            "COMPLETENESS WARNING: the completeness check itself failed to run "
            f"({type(exc).__name__}: {exc}) — this is a warning about the check, not the app."
        ]
