"""Tests for compact developer-agent validation reporting."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents" / "developer-agent"))

from developer_agent import (  # noqa: E402
    _extract_pytest_summary,
    _format_validation_failure,
    _format_validation_success,
)


def test_extract_pytest_summary_uses_result_line() -> None:
    stdout = "....\n\n29 passed in 0.42s"
    assert _extract_pytest_summary(stdout) == "29 passed in 0.42s"


def test_format_validation_success_single_block() -> None:
    report = _format_validation_success(
        ["deps", "structure", "import", "pytest"],
        [],
        pytest_summary="29 passed in 0.42s",
        health_routes=2,
    )
    assert report.startswith("All checks passed:")
    assert "29 passed in 0.42s" in report
    assert "2 GET route(s) probed" in report
    assert "DEPS OK" not in report


def test_format_validation_failure_shows_step_and_passed() -> None:
    report = _format_validation_failure(
        "import",
        "IMPORT FAILED: module not found",
        ["deps", "structure"],
        ["seed_bcrypt: placeholder"],
    )
    assert "Validation failed at import:" in report
    assert "Passed before failure: deps, structure" in report
    assert "seed_bcrypt: placeholder" in report
