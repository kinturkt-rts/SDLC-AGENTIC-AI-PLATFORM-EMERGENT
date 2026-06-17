---
name: code-review
description: Reviews pull requests and diffs for correctness, security, test quality, and architecture fit against project standards. Use for PR/MR review, pre-merge checks, regression risk assessment, or SonarQube follow-up.
disable-model-invocation: true
---

# Code Review

## When To Use

Cross-cutting workflow, not a runtime Strands agent. Apply when reviewing merge requests, validating pre-merge quality, or explaining risks in recent code changes.

**Cursor orchestrator:** Run `/code-reviewer` to delegate each step to subagents (see `.cursor/agents/code-reviewer.md` and `.cursor/agents/review-workers/`). The orchestrator must launch workers via the Task tool—one subagent per worker—never combine producer and verifier in the same run.

## Review Workflow

1. Confirm scope and intent from the issue/PR description.
2. Inspect changed files for behavioral correctness and regressions.
3. Check security, architecture boundaries, and maintainability.
4. Evaluate tests for coverage, quality, and realistic failure detection.
5. Return findings ordered by severity, then open questions, then a brief summary.

## Review Checklist

1. **Scope** — Changes match the Jira/task description; no unrelated edits.
2. **Correctness** — Logic handles expected paths, edge cases, and error cases.
3. **Security** — No secrets committed; input validation exists; least privilege for infra/IAM changes.
4. **Architecture** — Boundaries remain clear and dependency direction is not degraded.
5. **FastAPI** — Consistent with `target-apps/_template/` (typed routes, Pydantic v2 patterns, explicit error handling).
6. **Agent platform** — Shared payload contracts match `agents/_shared/schemas.py`; MCP usage aligns with `config/mcp/servers.json`.
7. **Tests** — Behavior changes include tests; test quality follows one-path-per-test and AAA guidance.
8. **Operational quality** — Error messages are diagnosable, and observability impact is considered.

## Output Format

Present review feedback in this order:

1. **Findings** (highest severity first)
   - `Critical`: must fix before merge (bugs, security, broken behavior)
   - `Major`: strong merge risk, likely regression, or missing required validation/tests
   - `Minor`: maintainability/style improvements that should be addressed soon
2. **Open Questions / Assumptions**
3. **Change Summary** (short)

For each finding include:

- affected file/symbol
- concrete risk or failure mode
- recommended fix direction

If no issues are found, explicitly state that and call out any residual risk or test gaps.

## MCP (Optional)

- **GitLab** — MR comments, pipeline status
- **SonarQube** — `user-sonarqube` when connected

## Project References

- Coding standards: [`CODING_STANDARDS.md`](../../../CODING_STANDARDS.md)
- Test quality rule: [`.cursor/rules/test-quality.mdc`](../../rules/test-quality.mdc)