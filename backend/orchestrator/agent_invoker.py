"""Pluggable agent invocation for the SDLC pipeline orchestrator.

Each step routes through ``invoke_agent`` which dispatches to one of:

* ``cli``      -- spawns the agent's Python module as a subprocess (today, local dev)
* ``a2a-http`` -- POSTs a JSON-RPC ``message/send`` to the AgentCore A2A endpoint
* ``dry-run``  -- simulates the step, writing placeholder artifacts so the
                  end-to-end wiring can be exercised without Bedrock credentials

The CLI flags below mirror the invocations in ``scripts/run-sdlc.ps1``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AgentConfig, OrchestratorConfig


@dataclass
class StepRequest:
    agent_name: str
    feature: str
    input_path: Path | None
    context_path: Path
    extra_cli_args: list[str]
    task_prompt: str
    extra_context: dict[str, Any]


@dataclass
class StepResult:
    transport: str
    summary: str
    raw: dict[str, Any] | None = None


class AgentInvocationError(RuntimeError):
    """Raised when an agent step fails. Message is surfaced in run state."""


def invoke_agent(
    request: StepRequest,
    *,
    cfg: OrchestratorConfig,
    agent_cfg: AgentConfig,
) -> StepResult:
    if agent_cfg.mode == "cli":
        return _invoke_cli(request, cfg=cfg, agent_cfg=agent_cfg)
    if agent_cfg.mode == "a2a-http":
        return _invoke_a2a_http(request, agent_cfg=agent_cfg)
    if agent_cfg.mode == "dry-run":
        return _invoke_dry_run(request, cfg=cfg)
    raise AgentInvocationError(f"Unsupported transport mode: {agent_cfg.mode}")


# ---------------------------------------------------------------------------
# Transport: cli (subprocess)
# ---------------------------------------------------------------------------

def _cli_module_path(repo_root: Path, agent_name: str) -> Path:
    module = f"agents/{agent_name}/{agent_name.replace('-', '_')}.py"
    return repo_root / module


def _invoke_cli(
    request: StepRequest,
    *,
    cfg: OrchestratorConfig,
    agent_cfg: AgentConfig,
) -> StepResult:
    module = agent_cfg.cli_module or str(_cli_module_path(cfg.repo_root, agent_cfg.name))
    cmd = [cfg.python_executable, module, *request.extra_cli_args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cfg.repo_root,
            capture_output=True,
            text=True,
            timeout=agent_cfg.timeout_sec,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AgentInvocationError(
            f"{agent_cfg.name}: python executable not found "
            f"({cfg.python_executable!r}). Set ORCHESTRATOR_PYTHON in env."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AgentInvocationError(
            f"{agent_cfg.name}: timed out after {agent_cfg.timeout_sec}s"
        ) from exc

    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-25:]
        raise AgentInvocationError(
            f"{agent_cfg.name} (cli) exited {proc.returncode}\n" + "\n".join(tail)
        )

    summary_lines = (proc.stdout or "").strip().splitlines()[-3:]
    return StepResult(
        transport="cli",
        summary="\n".join(summary_lines) or f"{agent_cfg.name} completed",
    )


# ---------------------------------------------------------------------------
# Transport: a2a-http (Bedrock AgentCore A2A endpoint)
# ---------------------------------------------------------------------------

def _invoke_a2a_http(request: StepRequest, *, agent_cfg: AgentConfig) -> StepResult:
    if not agent_cfg.url:
        raise AgentInvocationError(
            f"{agent_cfg.name}: a2a-http mode requires an URL "
            f"(set AGENT_URL_{agent_cfg.name.replace('-', '_').upper()} or config)."
        )

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": request.task_prompt}],
            },
            "metadata": {
                "feature": request.feature,
                "context": request.extra_context,
            },
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        agent_cfg.url.rstrip("/") + "/",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )

    try:
        with urlopen(req, timeout=agent_cfg.timeout_sec) as resp:
            raw_body = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        raise AgentInvocationError(
            f"{agent_cfg.name} (a2a-http) HTTP {exc.code}: {detail[:500]}"
        ) from exc
    except URLError as exc:
        raise AgentInvocationError(
            f"{agent_cfg.name} (a2a-http) connection error: {exc.reason}"
        ) from exc

    try:
        data = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        data = {"raw": raw_body[:500]}

    if "error" in data:
        raise AgentInvocationError(f"{agent_cfg.name} (a2a-http) error: {data['error']}")

    summary = _summarize_a2a_response(data) or f"{agent_cfg.name} completed"
    return StepResult(transport="a2a-http", summary=summary, raw=data)


def _summarize_a2a_response(data: dict[str, Any]) -> str:
    """Extract a short text summary from a JSON-RPC A2A response, best-effort."""
    result = data.get("result") or data
    parts = []
    if isinstance(result, dict):
        message = result.get("message") or result.get("status") or result
        for part in (message.get("parts") if isinstance(message, dict) else []) or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    text = "\n".join(parts).strip()
    return text[:400] if text else ""


# ---------------------------------------------------------------------------
# Transport: dry-run (testing the wiring without Bedrock)
# ---------------------------------------------------------------------------

def _invoke_dry_run(request: StepRequest, *, cfg: OrchestratorConfig) -> StepResult:
    """Simulate the agent's filesystem effect so downstream steps can proceed."""
    feature = request.feature
    repo = cfg.repo_root
    name = request.agent_name

    if name == "product-agent":
        prd = repo / "docs" / "PRD" / f"{feature}.md"
        prd.parent.mkdir(parents=True, exist_ok=True)
        prd.write_text(
            f"# {feature} (dry-run PRD)\n\nGenerated by orchestrator dry-run transport.\n",
            encoding="utf-8",
        )
        _write_context(
            repo,
            feature,
            {
                "targetApp": feature,
                "prdPath": f"docs/PRD/{feature}.md",
                "designDocPath": f"docs/design/{feature}.md",
                "diagramPaths": [f"docs/diagrams/generated-diagrams/{feature}.png"],
                "productAgentOutput": f"See prdPath for {feature} MVP requirements.",
                "inputPath": str(request.input_path.relative_to(repo).as_posix())
                if request.input_path
                else None,
            },
        )
        return StepResult(transport="dry-run", summary=f"PRD -> docs/PRD/{feature}.md")

    if name == "architect-agent":
        design = repo / "docs" / "design" / f"{feature}.md"
        design.parent.mkdir(parents=True, exist_ok=True)
        design.write_text(
            f"# {feature} architecture (dry-run)\n\n## 1. Overview\nGenerated by dry-run.\n",
            encoding="utf-8",
        )
        return StepResult(transport="dry-run", summary=f"design -> docs/design/{feature}.md")

    if name == "database-agent":
        sql_dir = repo / "target-apps" / feature / "db" / "sql"
        sql_dir.mkdir(parents=True, exist_ok=True)
        (sql_dir / "0001_init.sql").write_text(
            f"-- dry-run schema for {feature}\nCREATE TABLE IF NOT EXISTS hello (id INT);\n",
            encoding="utf-8",
        )
        return StepResult(
            transport="dry-run",
            summary=f"sql -> target-apps/{feature}/db/sql/0001_init.sql",
        )

    if name == "developer-agent":
        app_dir = repo / "target-apps" / feature / "app"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n\n"
            "@app.get('/health')\ndef health() -> dict:\n    return {'status': 'ok'}\n",
            encoding="utf-8",
        )
        handoff = repo / "agents" / "pipeline" / f"{feature}.developer-handoff.json"
        handoff.write_text(
            json.dumps(
                {"targetApp": feature, "writtenFiles": [f"target-apps/{feature}/app/main.py"]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return StepResult(transport="dry-run", summary=f"app -> target-apps/{feature}/app/main.py")

    if name == "gitlab-agent":
        handoff = repo / "agents" / "pipeline" / f"{feature}.gitlab-handoff.json"
        handoff.write_text(
            json.dumps(
                {
                    "targetApp": feature,
                    "branch": f"sdlc/{feature}",
                    "repoUrl": "https://code.example.com/sdlc/" + feature,
                    "dryRun": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return StepResult(transport="dry-run", summary=f"gitlab branch sdlc/{feature} (dry-run)")

    raise AgentInvocationError(f"dry-run: no simulation for agent {name!r}")


def _write_context(repo: Path, feature: str, fields: dict[str, Any]) -> None:
    ctx_path = repo / "agents" / "pipeline" / f"{feature}.context.json"
    ctx_path.parent.mkdir(parents=True, exist_ok=True)
    base: dict[str, Any] = {}
    if ctx_path.is_file():
        try:
            raw = ctx_path.read_text(encoding="utf-8")
            if raw.startswith("\ufeff"):
                raw = raw[1:]
            base = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            base = {}
    base.update({k: v for k, v in fields.items() if v is not None})
    if "targetApp" not in base:
        base["targetApp"] = feature
    ctx_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")


_ = sys  # keep `sys` import referenced for future stderr piping
