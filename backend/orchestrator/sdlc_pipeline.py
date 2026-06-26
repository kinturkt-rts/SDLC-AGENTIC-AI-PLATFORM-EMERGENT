"""Sequential SDLC pipeline orchestrator.

Replaces ``scripts/run-sdlc.ps1`` with a cross-platform Python entry that the
frontend can spawn (``POST /api/v1/runs/start``).

Steps (sequential, stops on first failure):

1. product-agent    --input-file inputs/<feature>.txt --prd-name <feature>
2. architect-agent  --target-app <feature> --context-file <ctx> --diagram-name <feature>
3. database-agent   --target-app <feature> --context-file <ctx>
4. developer-agent  --target-app <feature> --context-file <ctx>
5. gitlab-agent     --target-app <feature> --context-file <ctx>

Each step's transport (cli | a2a-http | dry-run) is resolved per-agent via
``config/orchestrator/agents.json`` plus env overrides (see ``config.py``).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .agent_invoker import (
    AgentInvocationError,
    StepRequest,
    StepResult,
    invoke_agent,
)
from .config import OrchestratorConfig, load_config
from .run_state import RunRecord, StepRecord, now_iso, write_state


SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


@dataclass
class StepDefinition:
    name: str
    label: str
    cli_args: Sequence[str]
    task_prompt: str
    extra_context: dict[str, object]


def build_steps(feature: str, *, input_path: Path, context_path: Path) -> list[StepDefinition]:
    repo_relative_input = input_path.as_posix()
    repo_relative_ctx = context_path.as_posix()
    return [
        StepDefinition(
            name="product-agent",
            label="1/5 Product (PRD)",
            cli_args=[
                "--input-file",
                repo_relative_input,
                "--prd-name",
                feature,
            ],
            task_prompt=(
                f"Read the requirements brief at {repo_relative_input} and produce the "
                f"PRD for feature '{feature}'. Write docs/PRD/{feature}.md and the "
                f"pipeline context JSON at {repo_relative_ctx}."
            ),
            extra_context={
                "feature": feature,
                "inputPath": repo_relative_input,
                "contextPath": repo_relative_ctx,
            },
        ),
        StepDefinition(
            name="architect-agent",
            label="2/5 Architect (design + diagram)",
            cli_args=[
                "--target-app",
                feature,
                "--context-file",
                repo_relative_ctx,
                "--diagram-name",
                feature,
                "--task",
                f"{feature} MVP",
            ],
            task_prompt=(
                f"Read the PRD via {repo_relative_ctx}.prdPath and produce "
                f"docs/design/{feature}.md plus the architecture diagram PNG."
            ),
            extra_context={"feature": feature, "contextPath": repo_relative_ctx},
        ),
        StepDefinition(
            name="database-agent",
            label="3/5 Database (SQL migrations)",
            cli_args=[
                "--target-app",
                feature,
                "--context-file",
                repo_relative_ctx,
                "--task",
                (
                    "Implement data model from designDocPath sections 3 and 6: numbered "
                    "sql/ migrations, dev seed (__BCRYPT_PLACEHOLDER__ for password "
                    "hashes), stable UUIDs, and HANDOFF.md."
                ),
            ],
            task_prompt=(
                f"Read design via {repo_relative_ctx}.designDocPath and produce SQL "
                f"migrations under target-apps/{feature}/db/sql/."
            ),
            extra_context={"feature": feature, "contextPath": repo_relative_ctx},
        ),
        StepDefinition(
            name="developer-agent",
            label="4/5 Developer (FastAPI)",
            cli_args=[
                "--target-app",
                feature,
                "--context-file",
                repo_relative_ctx,
                "--task",
                (
                    "Implement API surface from designDocPath as FastAPI routes. Read "
                    "db/HANDOFF.md and every db/sql/*.sql before models. Baseline "
                    "pytest must pass."
                ),
            ],
            task_prompt=(
                f"Read context {repo_relative_ctx} and produce the FastAPI service "
                f"under target-apps/{feature}/."
            ),
            extra_context={"feature": feature, "contextPath": repo_relative_ctx},
        ),
        StepDefinition(
            name="gitlab-agent",
            label="5/5 GitLab publish",
            cli_args=[
                "--target-app",
                feature,
                "--context-file",
                repo_relative_ctx,
            ],
            task_prompt=(
                f"Publish target-apps/{feature}/ and pipeline artifacts to the "
                f"sdlc/{feature} branch on GitLab; write gitlab-handoff.json."
            ),
            extra_context={"feature": feature, "contextPath": repo_relative_ctx},
        ),
    ]


def validate_feature(feature: str) -> str:
    if not SLUG_RE.match(feature):
        raise SystemExit(
            f"Invalid feature slug {feature!r}. Use lowercase letters, digits, and dashes; "
            f"start with a letter; max 64 chars."
        )
    return feature


def initial_record(feature: str, *, run_id: str, input_path: Path, steps: list[StepDefinition]) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        feature=feature,
        status="queued",
        triggered_by="frontend",
        started_at=None,
        input_path=input_path.as_posix(),
        steps=[StepRecord(name=s.name, label=s.label, status="queued") for s in steps],
    )


def _write(record: RunRecord, cfg: OrchestratorConfig) -> None:
    write_state(cfg.repo_root, record)


def run_pipeline(
    feature: str,
    *,
    input_path: Path,
    cfg: OrchestratorConfig | None = None,
    run_id: str | None = None,
) -> RunRecord:
    feature = validate_feature(feature)
    cfg = cfg or load_config()
    if not input_path.is_absolute():
        input_path = (cfg.repo_root / input_path).resolve()
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    context_path = cfg.repo_root / "agents" / "pipeline" / f"{feature}.context.json"
    steps = build_steps(
        feature,
        input_path=input_path.relative_to(cfg.repo_root),
        context_path=context_path.relative_to(cfg.repo_root),
    )

    record = initial_record(
        feature,
        run_id=run_id or f"run-{feature}",
        input_path=input_path.relative_to(cfg.repo_root),
        steps=steps,
    )
    record.status = "running"
    record.started_at = now_iso()
    _write(record, cfg)

    for step_def, step_state in zip(steps, record.steps, strict=True):
        agent_cfg = cfg.agents.get(step_def.name)
        if agent_cfg is None:
            step_state.status = "failed"
            step_state.error = f"No orchestrator config for {step_def.name}"
            record.status = "failed"
            record.error = step_state.error
            record.finished_at = now_iso()
            _write(record, cfg)
            return record

        step_state.status = "running"
        step_state.transport = agent_cfg.mode
        step_state.started_at = now_iso()
        record.current_step = step_def.name
        _write(record, cfg)

        request = StepRequest(
            agent_name=step_def.name,
            feature=feature,
            input_path=input_path,
            context_path=context_path,
            extra_cli_args=list(step_def.cli_args),
            task_prompt=step_def.task_prompt,
            extra_context=dict(step_def.extra_context),
        )

        started = time.monotonic()
        try:
            result: StepResult = invoke_agent(request, cfg=cfg, agent_cfg=agent_cfg)
        except AgentInvocationError as exc:
            step_state.status = "failed"
            step_state.error = str(exc)
            step_state.finished_at = now_iso()
            step_state.duration_sec = round(time.monotonic() - started, 2)
            record.status = "failed"
            record.error = f"{step_def.name}: {exc}"
            record.finished_at = now_iso()
            _write(record, cfg)
            return record
        except Exception as exc:  # noqa: BLE001 -- surface unexpected failures cleanly
            step_state.status = "failed"
            step_state.error = f"unexpected: {exc}\n{traceback.format_exc()[-500:]}"
            step_state.finished_at = now_iso()
            step_state.duration_sec = round(time.monotonic() - started, 2)
            record.status = "failed"
            record.error = step_state.error
            record.finished_at = now_iso()
            _write(record, cfg)
            return record

        step_state.status = "completed"
        step_state.transport = result.transport
        step_state.output_summary = result.summary
        step_state.finished_at = now_iso()
        step_state.duration_sec = round(time.monotonic() - started, 2)
        _write(record, cfg)

    record.status = "completed"
    record.current_step = None
    record.finished_at = now_iso()
    _write(record, cfg)
    return record


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SDLC pipeline orchestrator")
    parser.add_argument("--feature", required=True, help="Feature slug (e.g. inventory-app)")
    parser.add_argument("--input-file", required=True, help="Path to inputs/<feature>.txt")
    parser.add_argument("--run-id", help="Override the generated runId")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the final run record as JSON on stdout (for callers).",
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    input_path = Path(args.input_file)
    record = run_pipeline(
        args.feature,
        input_path=input_path,
        cfg=cfg,
        run_id=args.run_id,
    )

    if args.json:
        json.dump(record.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"[orchestrator] feature={record.feature} status={record.status}")
        for step in record.steps:
            print(f"  {step.label:35s} {step.status:9s} ({step.transport or '-'})")
        if record.error:
            print(f"  error: {record.error}", file=sys.stderr)

    return 0 if record.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
