"""Tests for developer-agent context enrichment and path guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_PATH = _REPO_ROOT / "agents" / "developer-agent" / "developer_agent.py"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("developer_agent", _AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_REPO_ROOT / "agents"))
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_path_rejects_template_escape_with_stray_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: a stray space in an LLM-authored path ("_template /x.json") let a
    write escape the golden-template guard and land as a bogus top-level S3 key
    (runs/<runId>/_template /scaffold-manifest.json) instead of being blocked. In
    cloud mode _resolve_repo_path permits writes anywhere under repo root, so the
    golden-template guard depends entirely on _validate_dev_write_path's part check —
    which the un-stripped space defeated (this reproduces the cloud codepath)."""
    mod = _load_agent_module()
    monkeypatch.setattr(mod, "_is_cloud_store", lambda: True)
    file_path = mod._resolve_repo_path("_template /scaffold-manifest.json", write=True)
    assert "_template" in file_path.parts
    blocked = mod._validate_dev_write_path(file_path)
    assert blocked is not None
    assert "read-only" in blocked


def test_resolve_repo_path_still_blocks_clean_template_path() -> None:
    mod = _load_agent_module()
    with pytest.raises(ValueError, match="read-only"):
        mod._resolve_repo_path("target-apps/_template/app/database.py", write=True)


def test_max_output_tokens_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("DEVELOPER_AGENT_MAX_TOKENS", raising=False)
    assert mod._max_output_tokens() == 32768
    monkeypatch.setenv("DEVELOPER_AGENT_MAX_TOKENS", "16384")
    assert mod._max_output_tokens() == 16384


def test_thinking_enabled_and_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    monkeypatch.delenv("DEVELOPER_AGENT_THINKING", raising=False)
    monkeypatch.delenv("DEVELOPER_AGENT_THINKING_BUDGET", raising=False)
    assert mod._thinking_enabled() is False
    assert mod._thinking_budget_tokens() == 8192
    monkeypatch.setenv("DEVELOPER_AGENT_THINKING", "1")
    monkeypatch.setenv("DEVELOPER_AGENT_THINKING_BUDGET", "4096")
    assert mod._thinking_enabled() is True
    assert mod._thinking_budget_tokens() == 4096


def test_enrich_developer_context_sets_db_backend_postgres() -> None:
    mod = _load_agent_module()
    ctx: dict[str, Any] = {
        "targetApp": "meeting-assistant",
        "preferredSqlPath": "target-apps/meeting-assistant/db/sql",
    }
    mod._enrich_developer_context(ctx)
    assert ctx["dbBackend"] == "postgres"


def test_enrich_developer_context_discovers_handoff_md(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    handoff_dir = tmp_path / "target-apps" / "meeting-assistant" / "db"
    handoff_dir.mkdir(parents=True)
    (handoff_dir / "HANDOFF.md").write_text("# DB handoff\n", encoding="utf-8")
    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / "README.md").write_text("template\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)

    ctx: dict[str, Any] = {"targetApp": "meeting-assistant"}
    mod._enrich_developer_context(ctx)
    assert ctx.get("databaseHandoffPath") == "target-apps/meeting-assistant/db/HANDOFF.md"


def test_enrich_developer_context_discovers_scraped_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    scraped = tmp_path / "docs" / "PRD" / "scraped" / "demo-api"
    scraped.mkdir(parents=True)
    (scraped / "competitor.md").write_text("# Competitor API\n", encoding="utf-8")

    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / "README.md").write_text("template\n", encoding="utf-8")

    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)

    ctx: dict[str, Any] = {"targetApp": "demo-api"}
    mod._enrich_developer_context(ctx)
    assert ctx["scrapedMarkdownPaths"] == ["docs/PRD/scraped/demo-api/competitor.md"]


def test_resolve_repo_path_allows_inputs_read() -> None:
    mod = _load_agent_module()
    path = mod._resolve_repo_path("inputs/team-faq-bot.txt", write=False)
    assert path.name == "team-faq-bot.txt"


def test_resolve_repo_path_blocks_writes_outside_target_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "local")
    with pytest.raises(ValueError, match="writes only allowed"):
        mod._resolve_repo_path("docs/design/foo.md", write=True)


def test_resolve_repo_path_blocks_template_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    monkeypatch.setenv("ARTIFACT_STORE", "s3")

    with pytest.raises(ValueError, match="read-only"):
        mod._resolve_repo_path("target-apps/_template/golden/generated.py", write=True)


def test_deployment_handoff_includes_port_and_env_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    env_example = service / ".env.example"
    env_example.write_text("API_KEY=placeholder\nDATABASE_URL=\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    written = ["target-apps/demo-api/.env.example"]
    handoff = mod._deployment_handoff("demo-api", written)
    assert handoff["targetEnvironment"] == "aws-dev"
    assert handoff["port"] == 8000
    assert handoff["healthCheckPath"] == "/health"
    assert "0.0.0.0" in handoff["containerEntrypoint"]
    assert "API_KEY" in handoff["envVarNames"]
    assert "PORT" in handoff["envVarNames"]


def test_strip_duplicate_handoff_sections() -> None:
    mod = _load_agent_module()
    text = (
        "Stack summary here.\n\n"
        "### 2. Files Written\n```\ntarget-apps/demo/app/main.py\n```\n\n"
        "### 6. Handoff JSON\n```json\n{\"writtenFiles\": [\"a.py\"]}\n```\n\n"
        "## Files written\n- `a.py`\n\n"
        "## Context handoff\n```json\n{\"writtenFiles\": [\"a.py\"]}\n```"
    )
    stripped = mod._strip_duplicate_handoff_sections(text)
    assert stripped == "Stack summary here."
    assert "writtenFiles" not in stripped


def test_dedupe_preserve_order() -> None:
    mod = _load_agent_module()
    assert mod._dedupe_preserve_order(["a.py", "b.py", "a.py"]) == ["a.py", "b.py"]


def test_failed_developer_handoff_is_written_without_files(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    captured: dict[str, Any] = {}

    def _capture(_app: str, handoff: dict[str, Any], *, context=None) -> str:
        captured.update(handoff)
        return "demo/handoffs/developer-handoff.json"

    monkeypatch.setattr(mod, "_write_developer_handoff", _capture)
    rel = mod._persist_developer_handoff(
        "demo",
        {"targetApp": "demo"},
        [],
        status="failed",
        error="model timeout",
    )

    assert rel is not None
    assert captured["status"] == "failed"
    assert captured["writtenFiles"] == []
    assert captured["error"] == "model timeout"


def test_validate_dev_write_path_blocks_env_and_qa_artifacts(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "tests").mkdir(parents=True)

    assert mod._validate_dev_write_path(service / ".env") is not None
    assert mod._validate_dev_write_path(service / ".env.local") is not None
    assert mod._validate_dev_write_path(service / ".env.example") is None
    assert mod._validate_dev_write_path(service / "QA_REPORT.md") is not None
    assert mod._validate_dev_write_path(service / "tests" / "test_qa_edge_cases.py") is not None
    assert mod._validate_dev_write_path(service / "tests" / "test_api.py") is None
    assert mod._validate_dev_write_path(service / ".venv" / "pyvenv.cfg") is not None


def test_validate_dev_write_path_blocks_verbatim_scaffold_files(tmp_path: Path) -> None:
    """Golden template files must come from dev_scaffold, not hand-written content —
    regression for a hand-rewritten app/startup_checks.py that shipped a syntax error."""
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "app" / "routers").mkdir(parents=True)
    (service / "app" / "models").mkdir(parents=True)

    assert mod._validate_dev_write_path(service / "app" / "database.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "startup_checks.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "routers" / "health.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "models" / "pg_types.py") is not None
    assert mod._validate_dev_write_path(service / "app" / "routers" / "items.py") is None


def test_validate_dev_write_path_blocks_all_template_files(tmp_path: Path) -> None:
    mod = _load_agent_module()
    template_file = tmp_path / "target-apps" / "_template" / "golden" / "database_golden.py"

    assert "read-only" in str(mod._validate_dev_write_path(template_file))
    assert "read-only" in mod.dev_scaffold("_template", "B")


def test_python_for_service_prefers_repo_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    repo_venv = tmp_path / ".venv" / "Scripts"
    repo_venv.mkdir(parents=True)
    repo_python = repo_venv / "python.exe"
    repo_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    assert mod._python_for_service(service) == str(repo_python)


def test_ensure_service_requirements_installed_runs_pip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    (service / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    import subprocess

    monkeypatch.setattr(subprocess, "run", _fake_run)
    ok, msg = mod._ensure_service_requirements_installed(service, "python")
    assert ok is True
    assert msg == ""
    assert calls[0][:4] == ["python", "-m", "pip", "install"]


def test_ensure_delivery_files_copies_template_seed_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "target-apps" / "demo-api"
    service.mkdir(parents=True)
    template = tmp_path / "target-apps" / "_template"
    template.mkdir(parents=True)
    (template / ".env.example").write_text("APP_ENV=test\n", encoding="utf-8")
    (template / "README.md").write_text("# Demo API\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod, "_TARGET_APPS", tmp_path / "target-apps")
    monkeypatch.setattr(mod, "_TEMPLATE_DIR", template)
    monkeypatch.setattr(mod, "_is_cloud_store", lambda: False)

    written = mod._ensure_delivery_files(
        "demo-api",
        ["target-apps/demo-api/app/main.py"],
        context=None,
    )
    assert "target-apps/demo-api/.env.example" in written
    assert "target-apps/demo-api/README.md" in written
    assert (service / ".env.example").read_text(encoding="utf-8") == "APP_ENV=test\n"
    assert (service / "README.md").read_text(encoding="utf-8") == "# Demo API\n"


def test_verbatim_scaffold_suffixes_is_subset_of_manifest_force_refresh() -> None:
    """Drift guard between two hand-maintained lists in different modules:
    developer_agent.py's _VERBATIM_SCAFFOLD_SUFFIXES (blocks LLM writes) and
    scaffold.py's manifest-derived always_refresh (force-copies on every
    dev_scaffold call). The block list must stay a subset of the force-refresh
    set — see the cross-reference comments at both definitions. If someone adds
    a file to the block list without also adding it to scaffold-manifest.json's
    copy_verbatim/copy_as (outside customize_after_scaffold), this fails.
    """
    mod = _load_agent_module()  # also puts agents/developer-agent on sys.path and imports scaffold
    import scaffold

    manifest_path = _REPO_ROOT / "target-apps" / "_template" / "scaffold-manifest.json"
    manifest = scaffold.load_manifest(manifest_path)
    customize = set(manifest.get("customize_after_scaffold", []))

    always_refresh: set[str] = set()
    for pattern in scaffold._VALID_PATTERNS:
        spec = scaffold.resolve_pattern_spec(manifest, pattern)
        always_refresh |= set(spec["copy_verbatim"]) | set(spec["copy_as"].values())
    always_refresh -= customize

    block_list = {"/".join(suffix) for suffix in mod._VERBATIM_SCAFFOLD_SUFFIXES}

    missing = block_list - always_refresh
    assert not missing, (
        "developer_agent.py's _VERBATIM_SCAFFOLD_SUFFIXES has entries not covered "
        "by scaffold.py's manifest-derived always_refresh set — the two lists have "
        f"drifted: {sorted(missing)}"
    )


# ── api-key mode: hardcoded single-header auth model ─────────────────────────


def test_validate_dev_write_path_blocks_app_auth_py_in_api_key_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """api-key mode has exactly one fixed auth file (app/dependencies.py) — the
    LLM must never be able to add a second one (app/auth.py) to smuggle in an
    invented header."""
    mod = _load_agent_module()
    monkeypatch.setattr(mod, "_current_auth_mode", lambda: "api-key")
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "app").mkdir(parents=True)

    blocked = mod._validate_dev_write_path(service / "app" / "auth.py")
    assert blocked is not None
    assert "forbidden" in blocked.lower()


def test_validate_dev_write_path_allows_app_auth_py_in_jwt_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app/auth.py block is api-key-only — jwt mode never had this file and
    must stay byte-identical (no new restriction leaking into the JWT path)."""
    mod = _load_agent_module()
    monkeypatch.setattr(mod, "_current_auth_mode", lambda: "jwt")
    service = tmp_path / "target-apps" / "demo-svc"
    (service / "app").mkdir(parents=True)

    assert mod._validate_dev_write_path(service / "app" / "auth.py") is None


def test_validate_users_auth_columns_requires_token_and_role_in_api_key_mode(
    tmp_path: Path,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    sql_dir = service / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "001_schema.sql").write_text(
        "CREATE TABLE users (id uuid PRIMARY KEY, username text);\n",
        encoding="utf-8",
    )

    errors = mod.validate_users_auth_columns(service, auth_mode="api-key")
    joined = "\n".join(errors)
    assert "token" in joined.lower()
    assert "role" in joined.lower()


def test_validate_users_auth_columns_passes_with_token_and_role(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    sql_dir = service / "db" / "sql"
    sql_dir.mkdir(parents=True)
    (sql_dir / "001_schema.sql").write_text(
        "CREATE TABLE users (id uuid PRIMARY KEY, token text UNIQUE, role text);\n",
        encoding="utf-8",
    )

    assert mod.validate_users_auth_columns(service, auth_mode="api-key") == []


def test_validate_no_invented_auth_headers_catches_bare_x_user_id_header(
    tmp_path: Path,
) -> None:
    """Regression for the bug that motivated this gate: a route declaring its
    own bare Header(alias="X-User-Id") instead of using the fixed
    app/dependencies.py::require_api_key."""
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app" / "routers").mkdir(parents=True)
    (service / "app" / "dependencies.py").write_text(
        "def require_api_key(): ...\n", encoding="utf-8"
    )
    (service / "app" / "routers" / "items.py").write_text(
        'from fastapi import Header\n'
        'def list_items(x_user_id: str = Header(alias="X-User-Id")): ...\n',
        encoding="utf-8",
    )

    errors = mod.validate_no_invented_auth_headers(service, "api-key")
    assert any("X-User-Id" in e for e in errors)


def test_validate_no_invented_auth_headers_catches_second_apikeyheader_scheme(
    tmp_path: Path,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app" / "routers").mkdir(parents=True)
    (service / "app" / "dependencies.py").write_text(
        "def require_api_key(): ...\n", encoding="utf-8"
    )
    (service / "app" / "auth.py").write_text(
        'from fastapi.security import APIKeyHeader\n'
        '_admin_key_scheme = APIKeyHeader(name="X-Admin-Key")\n',
        encoding="utf-8",
    )

    errors = mod.validate_no_invented_auth_headers(service, "api-key")
    assert any("app/auth.py" in e and "forbidden" in e.lower() for e in errors)
    assert any("APIKeyHeader" in e for e in errors)


def test_validate_no_invented_auth_headers_passes_clean_app(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app" / "routers").mkdir(parents=True)
    (service / "app" / "dependencies.py").write_text(
        'from fastapi.security import APIKeyHeader\n'
        '_api_key_scheme = APIKeyHeader(name="X-API-Key")\n'
        "def require_api_key(): ...\n"
        "def require_role(*roles): ...\n",
        encoding="utf-8",
    )
    (service / "app" / "routers" / "items.py").write_text(
        "from app.dependencies import require_api_key, require_role\n"
        "def list_items(current_user=Depends(require_api_key)): ...\n",
        encoding="utf-8",
    )

    assert mod.validate_no_invented_auth_headers(service, "api-key") == []


def test_validate_no_invented_auth_headers_noops_in_jwt_mode(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app").mkdir(parents=True)
    (service / "app" / "auth.py").write_text(
        'from fastapi import Header\n'
        'def x(x_user_id: str = Header(alias="X-User-Id")): ...\n',
        encoding="utf-8",
    )

    assert mod.validate_no_invented_auth_headers(service, "jwt") == []


def test_validate_api_key_route_usage_requires_require_api_key_or_require_role(
    tmp_path: Path,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    routers = service / "app" / "routers"
    routers.mkdir(parents=True)
    (routers / "items.py").write_text(
        "def list_items(): ...\n", encoding="utf-8"
    )

    errors = mod.validate_api_key_route_usage(service)
    assert errors and "NEVER APPLIED" in errors[0]

    (routers / "items.py").write_text(
        "def list_items(current_user=Depends(require_api_key)): ...\n",
        encoding="utf-8",
    )
    assert mod.validate_api_key_route_usage(service) == []


def test_validate_cors_configured_catches_missing_middleware(tmp_path: Path) -> None:
    """Regression for warehouse-inventory: app/main.py and app/config.py are
    LLM-authored (not force-refreshed from _template), so CORSMiddleware can
    silently drop out — leaving every browser OPTIONS preflight to 405."""
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app").mkdir(parents=True)
    (service / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8"
    )
    (service / "app" / "config.py").write_text(
        "class Settings:\n    app_env: str = 'production'\n", encoding="utf-8"
    )

    errors = mod.validate_cors_configured(service)
    assert any("CORS MIDDLEWARE MISSING" in e for e in errors)
    assert any("CORS_ORIGINS MISSING" in e for e in errors)


def test_validate_cors_configured_catches_imported_but_unregistered(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app").mkdir(parents=True)
    (service / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "app = FastAPI()\n",
        encoding="utf-8",
    )
    (service / "app" / "config.py").write_text(
        "    cors_origins: list[str] = Field(default_factory=lambda: ['*'])\n",
        encoding="utf-8",
    )

    errors = mod.validate_cors_configured(service)
    assert any("NOT REGISTERED" in e for e in errors)


def test_validate_cors_configured_passes_clean_app(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    (service / "app").mkdir(parents=True)
    (service / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "app = FastAPI()\n"
        "app.add_middleware(\n"
        "    CORSMiddleware,\n"
        "    allow_origins=settings.cors_origins,\n"
        "    allow_credentials=True,\n"
        "    allow_methods=['*'],\n"
        "    allow_headers=['*'],\n"
        ")\n",
        encoding="utf-8",
    )
    (service / "app" / "config.py").write_text(
        "    cors_origins: list[str] = Field(default_factory=lambda: ['*'], alias='CORS_ORIGINS')\n",
        encoding="utf-8",
    )

    assert mod.validate_cors_configured(service) == []


def test_validate_relationship_secondary_catches_bare_string(tmp_path: Path) -> None:
    """Regression: bookstore-inventory Author used secondary=\"book_authors\" under
    MetaData(schema=POSTGRES_SCHEMA) → first login query raised InvalidRequestError."""
    mod = _load_agent_module()
    service = tmp_path / "svc"
    models = service / "app" / "models"
    models.mkdir(parents=True)
    (models / "author.py").write_text(
        "from sqlalchemy.orm import relationship\n"
        'books = relationship("Book", secondary="book_authors", back_populates="authors")\n',
        encoding="utf-8",
    )

    errors = mod.validate_relationship_secondary(service)
    assert len(errors) == 1
    assert "RELATIONSHIP SECONDARY STRING" in errors[0]
    assert "book_authors" in errors[0]


def test_validate_relationship_secondary_catches_schema_qualified_string(
    tmp_path: Path,
) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    models = service / "app" / "models"
    models.mkdir(parents=True)
    (models / "author.py").write_text(
        'books = relationship("Book", secondary="bookstore_inventory.book_authors")\n',
        encoding="utf-8",
    )

    errors = mod.validate_relationship_secondary(service)
    assert any("bookstore_inventory.book_authors" in e for e in errors)


def test_validate_relationship_secondary_passes_table_object(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    models = service / "app" / "models"
    models.mkdir(parents=True)
    (models / "author.py").write_text(
        "from app.models.book import book_authors\n"
        'books = relationship("Book", secondary=book_authors, back_populates="authors")\n',
        encoding="utf-8",
    )
    (models / "book.py").write_text(
        "book_authors = Table('book_authors', Base.metadata)\n"
        'authors = relationship("Author", secondary=book_authors)\n',
        encoding="utf-8",
    )

    assert mod.validate_relationship_secondary(service) == []


def test_validate_relationship_secondary_noops_without_models_dir(tmp_path: Path) -> None:
    mod = _load_agent_module()
    service = tmp_path / "svc"
    service.mkdir()
    assert mod.validate_relationship_secondary(service) == []


def test_orm_column_category_array_of_string_is_array_not_string() -> None:
    """Regression: schema_parity false-failed every correctly-declared array column
    (DB TEXT[] <-> ORM ARRAY(String)) because "String" matched before "ARRAY" in the
    ordered keyword list. ARRAY must win over any inner type it wraps."""
    mod = _load_agent_module()
    assert mod._orm_column_category("ARRAY(String)") == "array"
    assert mod._orm_column_category("ARRAY(Text)") == "array"
    assert mod._orm_column_category("ARRAY(Integer)") == "array"
    assert mod._orm_column_category("ARRAY(pg_uuid_column())") == "array"
    # Non-array usages of the same inner keywords still resolve as before.
    assert mod._orm_column_category("String") == "string"
    assert mod._orm_column_category("Text") == "string"
    assert mod._orm_column_category("Integer") == "integer"


def test_db_column_category_array_matches_orm_array() -> None:
    mod = _load_agent_module()
    assert mod._db_column_category("ARRAY", "_text") == "array"
    assert mod._orm_column_category("ARRAY(String)") == mod._db_column_category("ARRAY", "_text")
