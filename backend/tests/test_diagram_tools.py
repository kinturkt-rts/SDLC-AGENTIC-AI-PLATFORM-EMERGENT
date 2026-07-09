"""Tests for diagram generation helpers."""

from __future__ import annotations

from _shared.diagram_tools import strip_mvp_from_diagram_title


def test_strip_mvp_from_diagram_title_double_quotes() -> None:
    code = 'with Diagram("Fitness Tracker MVP", filename=filename, show=False):'
    assert 'Diagram("Fitness Tracker"' in strip_mvp_from_diagram_title(code)
    assert "MVP" not in strip_mvp_from_diagram_title(code)


def test_strip_mvp_from_diagram_title_single_quotes() -> None:
    code = "with Diagram('FinOps MVP', filename=filename, show=False):"
    assert "Diagram('FinOps'" in strip_mvp_from_diagram_title(code)


def test_strip_mvp_from_diagram_title_unchanged_when_absent() -> None:
    code = 'with Diagram("Inventory App", filename=filename, show=False):'
    assert strip_mvp_from_diagram_title(code) == code
