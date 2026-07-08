"""Tests for frontend run elapsed resolution (mirrors frontend/src/lib/run-timing.ts)."""

from __future__ import annotations


def resolve_run_timings(
    *,
    started_at: str,
    status: str,
    live_started_at: str | None = None,
    live_finished_at: str | None = None,
    log_mtime_ms: int = 0,
    s3_latest_ms: int = 0,
    s3_earliest_ms: int = 0,
    telemetry_elapsed_sec: float | None = None,
    steps_duration_sec: float | None = None,
) -> tuple[str, str | None, int]:
    from datetime import datetime, timezone

    started_ms = datetime.fromisoformat(
        (live_started_at or started_at).replace("Z", "+00:00")
    ).timestamp() * 1000

    is_terminal = status in {"completed", "failed", "cancelled"}

    if (
        s3_earliest_ms > 0
        and s3_latest_ms > s3_earliest_ms + 60_000
        and live_started_at is None
        and abs(started_ms - s3_latest_ms) < 5000
    ):
        started_ms = float(s3_earliest_ms)

    if live_finished_at:
        finished_ms = datetime.fromisoformat(
            live_finished_at.replace("Z", "+00:00")
        ).timestamp() * 1000
        elapsed = max(1, int((finished_ms - started_ms) / 1000))
        return (
            datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc).isoformat(),
            live_finished_at,
            elapsed,
        )

    if not is_terminal:
        import time

        elapsed = max(1, int((time.time() * 1000 - started_ms) / 1000))
        return (
            datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc).isoformat(),
            None,
            elapsed,
        )

    end_ms = max(started_ms, float(log_mtime_ms or 0), float(s3_latest_ms or 0))
    elapsed = int((end_ms - started_ms) / 1000)

    if elapsed < 2 and telemetry_elapsed_sec and telemetry_elapsed_sec > 0:
        elapsed = round(telemetry_elapsed_sec)
        end_ms = started_ms + elapsed * 1000
    elif elapsed < 2 and steps_duration_sec and steps_duration_sec > 0:
        elapsed = round(steps_duration_sec)
        end_ms = started_ms + elapsed * 1000
    elif elapsed < 2 and s3_earliest_ms > 0 and s3_latest_ms > s3_earliest_ms:
        started_ms = float(s3_earliest_ms)
        end_ms = float(s3_latest_ms)
        elapsed = int((end_ms - started_ms) / 1000)

    elapsed = max(1, elapsed)
    return (
        datetime.fromtimestamp(started_ms / 1000, tz=timezone.utc).isoformat(),
        datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc).isoformat(),
        elapsed,
    )


def test_elapsed_uses_s3_span_when_start_equals_latest() -> None:
    earliest = 1_700_000_000_000
    latest = earliest + 891_000  # ~14m 51s
    _, _, elapsed = resolve_run_timings(
        started_at="2026-01-01T12:00:00.000Z",
        status="completed",
        s3_latest_ms=latest,
        s3_earliest_ms=earliest,
    )
    assert elapsed == 891


def test_elapsed_uses_telemetry_when_timestamps_collide() -> None:
    ts = 1_700_000_000_000
    _, _, elapsed = resolve_run_timings(
        started_at="2026-01-01T12:00:00.000Z",
        status="completed",
        s3_latest_ms=ts,
        s3_earliest_ms=ts,
        telemetry_elapsed_sec=705.56,
    )
    assert elapsed == 706


def test_elapsed_honors_live_finished_at() -> None:
    _, finished, elapsed = resolve_run_timings(
        started_at="2026-01-01T12:00:00.000Z",
        status="completed",
        live_started_at="2026-01-01T12:00:00.000Z",
        live_finished_at="2026-01-01T12:14:51.000Z",
    )
    assert finished == "2026-01-01T12:14:51.000Z"
    assert elapsed == 891
