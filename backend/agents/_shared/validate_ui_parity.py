"""Validate API completeness against the design doc's declared route surface."""

from __future__ import annotations

from pathlib import Path

from _shared.api_surface import (
    collect_implemented_routes,
    collection_prefix_for_post,
    design_doc_for_app,
    has_get_list_for_prefix,
    parse_design_api_surface,
    paths_match,
)


def check_design_routes_implemented(
    app_dir: Path,
    repo_root: Path,
    app_slug: str,
) -> list[str]:
    """Every route in design §4 must exist in FastAPI routers."""
    design_path = design_doc_for_app(app_slug, repo_root)
    if not design_path:
        return []
    design_routes = parse_design_api_surface(design_path)
    if not design_routes:
        return []
    implemented = collect_implemented_routes(app_dir)
    errors: list[str] = []
    for method, path in design_routes:
        if any(m == method and paths_match(path, p) for m, p in implemented):
            continue
        rel = design_path.relative_to(repo_root).as_posix()
        errors.append(
            f"API_SURFACE: design route missing in code — {method} {path} "
            f"(see {rel} §4)"
        )
    return errors


def check_post_create_has_list_get(app_dir: Path) -> list[str]:
    """POST on a collection without GET list breaks browse/dropdown UX."""
    routes = collect_implemented_routes(app_dir)
    errors: list[str] = []
    seen: set[str] = set()
    for method, path in routes:
        prefix = collection_prefix_for_post(method, path)
        if not prefix or prefix in seen:
            continue
        seen.add(prefix)
        if not has_get_list_for_prefix(routes, prefix):
            errors.append(
                f"API_SURFACE: POST {prefix} exists but GET {prefix} list is missing — "
                "add a paginated GET for list views/dropdowns"
            )
    return errors


def validate_ui_parity(app_dir: Path, repo_root: Path) -> list[str]:
    """Run API parity checks against the design doc's declared route surface."""
    app_slug = app_dir.name
    errors: list[str] = []
    errors.extend(check_design_routes_implemented(app_dir, repo_root, app_slug))
    errors.extend(check_post_create_has_list_get(app_dir))
    return errors


def validate_ui_parity_blocking(app_dir: Path, repo_root: Path) -> list[str]:
    """Blocking errors only (excludes WARN lines)."""
    return [e for e in validate_ui_parity(app_dir, repo_root) if " WARN:" not in e]
