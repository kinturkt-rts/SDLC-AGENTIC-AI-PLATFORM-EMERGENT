"""Parse design API surface and collect FastAPI / Streamlit HTTP usage."""

from __future__ import annotations

import re
from pathlib import Path

_DESIGN_SURFACE_HEADER = re.compile(
    r"^##\s*4\.\s*API\s+surface\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_DESIGN_ROW = re.compile(
    r"^\|\s*(GET|POST|PATCH|PUT|DELETE)\s*\|\s*`([^`]+)`\s*\|",
    re.MULTILINE | re.IGNORECASE,
)
_ROUTER_DECORATOR = re.compile(
    r"@router\.(get|post|patch|put|delete)\(\s*[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)
_INCLUDE_ROUTER = re.compile(
    r"include_router\(\s*(\w+)\.router\s*,\s*prefix\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_INCLUDE_ROUTER_BARE = re.compile(
    r"include_router\(\s*(\w+)\.router\s*\)",
    re.IGNORECASE,
)
_STREAMLIT_HTTP = re.compile(
    r"_(?:get|post|patch|delete)\(\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_RAW_UUID_INPUT = re.compile(
    r"st\.text_input\(\s*[\"'][^\"']*"
    r"(?:\bID\b|_id\b|site_id|location_id|assignee|work_order)",
    re.IGNORECASE,
)
_PATH_PARAM = re.compile(r"\{[^}]+\}")


def _normalize_path(path: str) -> str:
    p = path.strip().rstrip("/") or "/"
    if not p.startswith("/"):
        p = "/" + p
    return p


def _path_to_pattern(path: str) -> str:
    """`/api/v1/items/{id}` -> `/api/v1/items/{*}` for matching."""
    return _PATH_PARAM.sub("{*}", _normalize_path(path))


def paths_match(design_path: str, implemented_path: str) -> bool:
    return _path_to_pattern(design_path) == _path_to_pattern(implemented_path)


def parse_design_api_surface(design_path: Path) -> list[tuple[str, str]]:
    """Return [(METHOD, path), ...] from design doc §4 table."""
    if not design_path.is_file():
        return []
    text = design_path.read_text(encoding="utf-8", errors="replace")
    header = _DESIGN_SURFACE_HEADER.search(text)
    if not header:
        return []
    section = text[header.end() : header.end() + 12000]
    rows: list[tuple[str, str]] = []
    for match in _DESIGN_ROW.finditer(section):
        method = match.group(1).upper()
        path = _normalize_path(match.group(2))
        rows.append((method, path))
    return rows


def is_collection_list_route(method: str, path: str) -> bool:
    """GET on a collection (no path params) — browse tables / dropdown sources."""
    if method.upper() != "GET":
        return False
    if path in ("/health", "/"):
        return False
    if path.startswith("/api/v1/auth"):
        return False
    return "{" not in path


def is_streamlit_ui_route(method: str, path: str) -> bool:
    """GET routes Streamlit should consume when Pattern C is required."""
    if not is_collection_list_route(method, path):
        return False
    # Detail/nested comment threads are optional in MVP Streamlit — wired per-work-order later.
    if "/comments" in path:
        return False
    return True


def collect_implemented_routes(app_dir: Path) -> set[tuple[str, str]]:
    """Scan routers + main.py prefixes into (METHOD, full_path)."""
    main_path = app_dir / "app" / "main.py"
    if not main_path.is_file():
        return set()

    main_text = main_path.read_text(encoding="utf-8", errors="replace")
    prefix_by_module: dict[str, str] = {}
    for match in _INCLUDE_ROUTER.finditer(main_text):
        prefix_by_module[match.group(1)] = _normalize_path(match.group(2))
    for match in _INCLUDE_ROUTER_BARE.finditer(main_text):
        module = match.group(1)
        if module == "health":
            prefix_by_module.setdefault(module, "")

    routes: set[tuple[str, str]] = set()
    routers_dir = app_dir / "app" / "routers"
    if not routers_dir.is_dir():
        return routes

    for router_file in routers_dir.glob("*.py"):
        if router_file.name.startswith("_"):
            continue
        module = router_file.stem
        prefix = prefix_by_module.get(module, "")
        text = router_file.read_text(encoding="utf-8", errors="replace")
        for dec in _ROUTER_DECORATOR.finditer(text):
            method = dec.group(1).upper()
            sub = dec.group(2)
            if sub in ("", "/"):
                full = _normalize_path(prefix) if prefix else "/"
            else:
                full = _normalize_path(f"{prefix}/{sub}" if prefix else sub)
            if module == "health" and method == "GET":
                full = "/health"
            routes.add((method, full))

    return routes


def collect_streamlit_api_calls(app_dir: Path) -> set[str]:
    ui = app_dir / "ui" / "streamlit_app.py"
    if not ui.is_file():
        return set()
    text = ui.read_text(encoding="utf-8", errors="replace")
    return {_normalize_path(p) for p in _STREAMLIT_HTTP.findall(text)}


def collection_prefix_for_post(method: str, path: str) -> str | None:
    """POST `/api/v1/sites` -> `/api/v1/sites` collection prefix needing GET list."""
    if method.upper() != "POST":
        return None
    if "{" in path:
        return None
    if path.startswith("/api/v1/auth"):
        return None
    return _normalize_path(path)


def has_get_list_for_prefix(routes: set[tuple[str, str]], prefix: str) -> bool:
    target = _normalize_path(prefix)
    for method, path in routes:
        if method == "GET" and paths_match(target, path):
            return True
    return False


def streamlit_calls_path(calls: set[str], path: str) -> bool:
    target = _normalize_path(path)
    for call in calls:
        if paths_match(target, call):
            return True
    return False


def find_raw_uuid_inputs(streamlit_path: Path) -> list[str]:
    if not streamlit_path.is_file():
        return []
    text = streamlit_path.read_text(encoding="utf-8", errors="replace")
    return [m.group(0) for m in _RAW_UUID_INPUT.finditer(text)]


def design_doc_for_app(app_slug: str, repo_root: Path) -> Path | None:
    candidate = repo_root / "docs" / "design" / f"{app_slug}.md"
    return candidate if candidate.is_file() else None
