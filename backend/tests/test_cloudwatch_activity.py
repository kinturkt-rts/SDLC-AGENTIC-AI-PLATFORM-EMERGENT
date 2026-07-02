"""Tests for CloudWatch activity line parsing (mirrors frontend cloudwatch-activity.ts)."""

from __future__ import annotations

import re

TOOL_LINE_RE = re.compile(r"\[([a-z-]+-agent)\]\s*Tool(?:\s*#(\d+))?:\s*(\S+)", re.I)
TOOL_BARE_RE = re.compile(r"Tool(?:\s*#(\d+))?:\s*(\S+)", re.I)


def summarize_activity_line(message: str) -> str | None:
    trimmed = message.strip()
    if not trimmed or len(trimmed) < 4:
        return None
    if re.search(r"starting server|uvicorn|healthcheck", trimmed, re.I):
        return None

    m = TOOL_LINE_RE.search(trimmed)
    if m:
        return f"Tool call — {m.group(3)}"

    m = TOOL_BARE_RE.search(trimmed)
    if m:
        return f"Tool call — {m.group(2)}"

    bracket = re.match(r"^\[([a-z-]+-agent)\]\s*(.+)$", trimmed, re.I)
    if bracket:
        body = bracket.group(2).strip()
        if body and not re.match(r"^tool(?:\s*#\d+)?:", body, re.I):
            return body[:140]

    if "traceback" in trimmed.lower():
        return "Agent error — see CloudWatch logs"

    return trimmed[:140] if len(trimmed) <= 200 else None


def test_tool_line_with_agent_prefix() -> None:
    assert (
        summarize_activity_line("[product-agent] Tool #3: gitlab_list_projects")
        == "Tool call — gitlab_list_projects"
    )


def test_tool_line_bare() -> None:
    assert summarize_activity_line("Tool: write_file") == "Tool call — write_file"


def test_skips_server_noise() -> None:
    assert summarize_activity_line("INFO: Starting server process") is None


def test_agent_bracket_message() -> None:
    assert (
        summarize_activity_line("[architect-agent] Generating architecture diagram")
        == "Generating architecture diagram"
    )
