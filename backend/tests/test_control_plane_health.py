"""Tests for control-plane health check detection."""

from _shared.control_plane_health import is_control_plane_health_check


def test_health_check_prefix_is_detected() -> None:
    msg = "Control-plane health check only. Do not run tools. Reply with exactly: OK"
    assert is_control_plane_health_check(msg) is True


def test_normal_pipeline_message_is_not_health_check() -> None:
    assert is_control_plane_health_check("Run run_sdlc_pipeline with inventory-app") is False
