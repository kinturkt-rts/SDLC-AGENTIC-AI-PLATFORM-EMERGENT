"""Validate API completeness vs design and Streamlit coverage (Pattern C only)."""

from __future__ import annotations

from pathlib import Path

from _shared.api_surface import (
    collect_implemented_routes,
    collect_streamlit_api_calls,
    collection_prefix_for_post,
    design_doc_for_app,
    find_raw_uuid_inputs,
    has_get_list_for_prefix,
    is_streamlit_ui_route,
    parse_design_api_surface,
    paths_match,
    requires_streamlit,
    streamlit_calls_path,
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


def check_post_create_has_list_get(
    app_dir: Path,
    *,
    streamlit_required: bool,
) -> list[str]:
    """POST on a collection without GET list breaks browse/dropdown UX."""
    if not streamlit_required:
        return []
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
                "add paginated GET for Streamlit tables/selectboxes"
            )
    return errors


def check_streamlit_list_coverage(
    app_dir: Path,
    repo_root: Path,
    app_slug: str,
) -> list[str]:
    """Streamlit must _get() every design §4 collection GET (browse/dashboard)."""
    ui = app_dir / "ui" / "streamlit_app.py"
    if not ui.is_file():
        return [
            f"UI_PARITY: deliveryProfile requires Streamlit but {app_dir.name}/ui/streamlit_app.py is missing"
        ]
    design_path = design_doc_for_app(app_slug, repo_root)
    design_routes = (
        parse_design_api_surface(design_path) if design_path else []
    )
    calls = collect_streamlit_api_calls(app_dir)
    errors: list[str] = []

    required_gets = [
        (m, p)
        for m, p in design_routes
        if is_streamlit_ui_route(m, p)
    ]
    if not required_gets:
        # Fallback: any implemented collection GET under /api/v1
        routes = collect_implemented_routes(app_dir)
        required_gets = [
            (m, p) for m, p in routes if is_streamlit_ui_route(m, p)
        ]

    for method, path in required_gets:
        if streamlit_calls_path(calls, path):
            continue
        errors.append(
            f"UI_PARITY: Streamlit never calls {method} {path} — add a role view "
            f"(table or st.selectbox data source) in ui/streamlit_app.py"
        )
    return errors


def check_streamlit_no_raw_uuid_fields(
    app_dir: Path,
    *,
    streamlit_required: bool,
) -> list[str]:
    if not streamlit_required:
        return []
    ui = app_dir / "ui" / "streamlit_app.py"
    routes = collect_implemented_routes(app_dir)
    list_prefixes = [
        p for m, p in routes if is_streamlit_ui_route(m, p)
    ]
    if not list_prefixes:
        return []
    raw = find_raw_uuid_inputs(ui)
    if not raw:
        return []
    return [
        "UI_PARITY: Streamlit uses st.text_input for IDs "
        f"({raw[0][:60]}...) but list GET APIs exist — use st.selectbox "
        "fed from _get() list endpoints"
    ]


def check_streamlit_no_deprecated_width_api(app_dir: Path) -> list[str]:
    """Block deprecated use_container_width (Streamlit 1.41+ prefers width=)."""
    ui = app_dir / "ui" / "streamlit_app.py"
    if not ui.is_file():
        return []
    text = ui.read_text(encoding="utf-8", errors="replace")
    if "use_container_width" not in text:
        return []
    return [
        "UI_PARITY: ui/streamlit_app.py uses deprecated `use_container_width` — "
        'replace True with width="stretch" and False with width="content"'
    ]


def validate_ui_parity(app_dir: Path, repo_root: Path) -> list[str]:
    """Run API/UI parity checks. Streamlit rules apply only when Pattern C is required."""
    app_slug = app_dir.name
    streamlit_required = requires_streamlit(app_slug, app_dir, repo_root)

    errors: list[str] = []
    errors.extend(check_design_routes_implemented(app_dir, repo_root, app_slug))
    errors.extend(
        check_post_create_has_list_get(app_dir, streamlit_required=streamlit_required)
    )

    if streamlit_required:
        errors.extend(check_streamlit_list_coverage(app_dir, repo_root, app_slug))
        errors.extend(
            check_streamlit_no_raw_uuid_fields(
                app_dir, streamlit_required=streamlit_required
            )
        )
    errors.extend(check_streamlit_no_deprecated_width_api(app_dir))
    if not streamlit_required and (app_dir / "ui" / "streamlit_app.py").is_file():
        errors.append(
            f"UI_PARITY WARN: {app_slug} has ui/streamlit_app.py but "
            "deliveryProfile.requiresStreamlit is false — API-only apps should omit ui/"
        )

    return errors


def validate_ui_parity_blocking(app_dir: Path, repo_root: Path) -> list[str]:
    """Blocking errors only (excludes WARN lines)."""
    return [e for e in validate_ui_parity(app_dir, repo_root) if " WARN:" not in e]
