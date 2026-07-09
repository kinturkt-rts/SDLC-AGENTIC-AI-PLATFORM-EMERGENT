"""Static checks for tests/conftest.py — catches import shadowing before pytest runs."""

from __future__ import annotations

import re
from pathlib import Path


def _uses_bare_app_dependency_overrides(text: str) -> bool:
    """True when conftest uses `app.dependency_overrides`, not `fastapi_app.dependency_overrides`."""
    return bool(re.search(r"(?<![\w.])app\.dependency_overrides", text))


def validate_conftest(service_dir: Path) -> list[str]:
    """Return blocking errors for conftest patterns that break TestClient setup."""
    conftest = service_dir / "tests" / "conftest.py"
    if not conftest.is_file():
        return []

    text = conftest.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    imports_app_submodule = bool(re.search(r"^import app\.\w+", text, re.MULTILINE))
    uses_bare_app_overrides = _uses_bare_app_dependency_overrides(text)
    uses_fastapi_app_alias = "from app.main import app as fastapi_app" in text
    uses_fastapi_app_overrides = "fastapi_app.dependency_overrides" in text

    if imports_app_submodule:
        if not uses_fastapi_app_alias:
            errors.append(
                "tests/conftest.py: module-level `import app.<submodule>` (e.g. "
                "`import app.models`) rebinds local name `app` to the package. "
                "Use `from app.main import app as fastapi_app`."
            )
        if uses_bare_app_overrides and not uses_fastapi_app_overrides:
            errors.append(
                "tests/conftest.py: after `import app.models`, use "
                "`fastapi_app.dependency_overrides[...]` and `TestClient(fastapi_app)` — "
                "not bare `app.dependency_overrides`."
            )

    tests_dir = service_dir / "tests"
    has_tests = tests_dir.is_dir() and any(tests_dir.glob("test_*.py"))
    has_pytest_ini = (service_dir / "pytest.ini").is_file()
    pyproject = service_dir / "pyproject.toml"
    has_pyproject_pytest = False
    if pyproject.is_file():
        has_pyproject_pytest = "[tool.pytest.ini_options]" in pyproject.read_text(
            encoding="utf-8",
            errors="replace",
        )
    if has_tests and not has_pytest_ini and not has_pyproject_pytest:
        errors.append(
            "Missing pytest.ini with `pythonpath = .` and `testpaths = tests` — "
            "without it, pytest raises ModuleNotFoundError: No module named 'app'."
        )

    return errors


def validate_conftest_reference(template_dir: Path) -> list[str]:
    """Validate golden conftest_reference.py (platform CI guard)."""
    ref = template_dir / "tests" / "conftest_reference.py"
    if not ref.is_file():
        return [f"Missing {ref.name} under {template_dir.as_posix()}"]

    text = ref.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    if "from app.main import app as fastapi_app" not in text:
        errors.append("conftest_reference.py must use `from app.main import app as fastapi_app`")
    if "fastapi_app.dependency_overrides" not in text:
        errors.append("conftest_reference.py must wire overrides via fastapi_app")
    if _uses_bare_app_dependency_overrides(text):
        errors.append("conftest_reference.py must not use bare `app.dependency_overrides`")
    if "import app.models" not in text:
        errors.append("conftest_reference.py must include `import app.models` for ORM registration")
    return errors
