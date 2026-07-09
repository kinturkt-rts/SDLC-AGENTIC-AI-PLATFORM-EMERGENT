"""Tests for conftest scaffold validation (import shadowing guard)."""

from __future__ import annotations

from pathlib import Path

from _shared.validate_conftest import validate_conftest, validate_conftest_reference

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE_DIR = _REPO_ROOT / "target-apps" / "_template"


def test_conftest_reference_template_is_valid() -> None:
    errors = validate_conftest_reference(_TEMPLATE_DIR)
    assert errors == [], "\n".join(errors)


def test_validate_conftest_rejects_import_models_with_bare_app(tmp_path: Path) -> None:
    service = tmp_path / "demo-api"
    tests = service / "tests"
    tests.mkdir(parents=True)
    (tests / "test_health.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (service / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    (tests / "conftest.py").write_text(
        "from app.main import app\n"
        "import app.models\n"
        "from app.database import get_db\n"
        "def client():\n"
        "    app.dependency_overrides[get_db] = lambda: None\n",
        encoding="utf-8",
    )
    errors = validate_conftest(service)
    assert any("fastapi_app" in e for e in errors)


def test_validate_conftest_accepts_fastapi_app_alias(tmp_path: Path) -> None:
    service = tmp_path / "demo-api"
    tests = service / "tests"
    tests.mkdir(parents=True)
    (tests / "test_health.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (service / "pytest.ini").write_text("[pytest]\npythonpath = .\n", encoding="utf-8")
    (tests / "conftest.py").write_text(
        "from app.main import app as fastapi_app\n"
        "import app.models\n"
        "from app.database import get_db\n"
        "def client():\n"
        "    fastapi_app.dependency_overrides[get_db] = lambda: None\n",
        encoding="utf-8",
    )
    assert validate_conftest(service) == []


def test_validate_conftest_requires_pytest_ini_when_tests_exist(tmp_path: Path) -> None:
    service = tmp_path / "demo-api"
    tests = service / "tests"
    tests.mkdir(parents=True)
    (tests / "test_health.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (tests / "conftest.py").write_text("# minimal\n", encoding="utf-8")
    errors = validate_conftest(service)
    assert any("pytest.ini" in e for e in errors)
