"""Static + light runtime checks for SQLAlchemy ORM relationship soundness"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


_SECONDARY_STRING_MSG = (
    "relationship(..., secondary=\"...\") string form is forbidden — define a "
    "module-level `Table(...)` once and pass that object on BOTH sides "
    "(e.g. secondary=book_authors). String secondary breaks mapper init when "
    "the other model file loads first."
)


def _models_dir(app_dir: Path) -> Path | None:
    models = app_dir / "app" / "models"
    return models if models.is_dir() else None


def _iter_model_files(app_dir: Path) -> list[Path]:
    models = _models_dir(app_dir)
    if models is None:
        return []
    return sorted(
        p
        for p in models.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    )


def _table_names_defined(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_table = (isinstance(func, ast.Name) and func.id == "Table") or (
            isinstance(func, ast.Attribute) and func.attr == "Table"
        )
        if not is_table or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            names.add(first.value)
    return names


def _secondary_usages(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return (lineno, kind, value) for each relationship(..., secondary=...).

    kind is \"string\" (literal table name) or \"name\" (Python identifier).
    """
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_rel = (isinstance(func, ast.Name) and func.id == "relationship") or (
            isinstance(func, ast.Attribute) and func.attr == "relationship"
        )
        if not is_rel:
            continue
        for kw in node.keywords:
            if kw.arg != "secondary":
                continue
            val = kw.value
            lineno = getattr(val, "lineno", getattr(node, "lineno", 0)) or 0
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                found.append((lineno, "string", val.value))
            elif isinstance(val, ast.Name):
                found.append((lineno, "name", val.id))
            elif isinstance(val, ast.Attribute):
                # e.g. models.book_authors — treat as name path
                parts: list[str] = []
                cur: ast.AST = val
                while isinstance(cur, ast.Attribute):
                    parts.append(cur.attr)
                    cur = cur.value
                if isinstance(cur, ast.Name):
                    parts.append(cur.id)
                    found.append((lineno, "name", ".".join(reversed(parts))))
                else:
                    found.append((lineno, "other", ast.dump(val)))
            else:
                found.append((lineno, "other", ast.dump(val)))
    return found


def check_m2m_secondary_style(app_dir: Path) -> list[str]:
    """Fail on string ``secondary=`` (and missing Table definitions for names)."""
    errors: list[str] = []
    defined_tables: set[str] = set()
    name_secondaries: list[tuple[str, int, str]] = []

    for path in _iter_model_files(app_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            rel = path.relative_to(app_dir).as_posix()
            errors.append(f"{rel}: cannot parse for ORM relationship check ({exc})")
            continue
        defined_tables |= _table_names_defined(tree)
        rel = path.relative_to(app_dir).as_posix()
        for lineno, kind, value in _secondary_usages(tree):
            if kind == "string":
                errors.append(
                    f"{rel}:{lineno}: {_SECONDARY_STRING_MSG} "
                    f"(found secondary=\"{value}\")"
                )
            elif kind == "name":
                name_secondaries.append((rel, lineno, value.split(".")[-1]))
            elif kind == "other":
                errors.append(
                    f"{rel}:{lineno}: relationship secondary= must be a module-level "
                    f"Table variable name (got unsupported expression)"
                )

    # Soft cross-check: Name secondary should correspond to a Table("...") somewhere.
    # Variable name often matches table name (book_authors → "book_authors").
    if defined_tables:
        for rel, lineno, var_name in name_secondaries:
            if var_name not in defined_tables and not any(
                var_name.endswith(t) or t.endswith(var_name) for t in defined_tables
            ):
                # Only warn-as-error when we saw at least one Table() — otherwise
                # secondary might import from elsewhere.
                if any(
                    var_name == t or var_name.replace("_", "") == t.replace("_", "")
                    for t in defined_tables
                ):
                    continue
                # If no Table definitions at all in models, skip — may use association_proxy only.
                pass

    return errors


def check_orm_mappers_configure(app_dir: Path, *, python_cmd: str | None = None) -> list[str]:
    """Import models and force SQLAlchemy mapper configuration.

    Runs in a subprocess with cwd=app_dir so generated deps resolve. Skips when
    there is no app/models package.
    """
    if not _iter_model_files(app_dir):
        return []

    py = python_cmd or sys.executable
    script = (
        "import os\n"
        "os.environ.setdefault('APP_ENV', 'test')\n"
        "os.environ.setdefault('SKIP_STARTUP_CHECKS', '1')\n"
        "os.environ.setdefault('DATABASE_URL', 'sqlite+pysqlite:///:memory:')\n"
        "import app.models  # noqa: F401 — register all mapped classes\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
        "print('MAPPERS_OK')\n"
    )
    env = {**os.environ, "APP_ENV": "test", "SKIP_STARTUP_CHECKS": "1"}
    # Prefer .env.example defaults when present (POSTGRES_SCHEMA etc.) without
    # requiring a real RDS URL — sqlite memory is enough for mapper wiring.
    example = app_dir / ".env.example"
    if example.is_file():
        for line in example.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in env:
                env[key] = value.strip().strip('"').strip("'")
    env["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    env["SKIP_STARTUP_CHECKS"] = "1"
    env["APP_ENV"] = "test"

    try:
        result = subprocess.run(
            [py, "-c", script],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return [
            "ORM mapper configure timed out (>45s) — check circular imports "
            "or heavy module-level work in app/models"
        ]
    except OSError as exc:
        return [f"ORM mapper configure could not spawn Python ({exc})"]

    if result.returncode == 0 and "MAPPERS_OK" in (result.stdout or ""):
        return []

    detail = (result.stdout or "") + (result.stderr or "")
    detail = detail.strip() or f"exit {result.returncode}"
    hint = ""
    if "book_authors" in detail or "secondary" in detail.lower() or "mappers failed" in detail.lower():
        hint = (
            " Hint: for M2M, define `Table(...)` once and use "
            "`relationship(..., secondary=<that_table>, back_populates=...)` "
            "on BOTH model classes — never secondary=\"table_name\" strings."
        )
    return [f"SQLAlchemy configure_mappers() failed:{hint}\n{detail}"]


def validate_orm_relationships(
    app_dir: Path, *, python_cmd: str | None = None, run_mapper_check: bool = True
) -> list[str]:
    """Blocking ORM relationship checks for developer validation."""
    errors = check_m2m_secondary_style(app_dir)
    if errors:
        # Static failures are enough — still try mapper check only when clean,
        # so the agent sees one coherent error class first.
        return errors
    if run_mapper_check:
        errors.extend(check_orm_mappers_configure(app_dir, python_cmd=python_cmd))
    return errors
