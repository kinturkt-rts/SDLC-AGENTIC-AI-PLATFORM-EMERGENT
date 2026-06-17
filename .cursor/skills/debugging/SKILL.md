---
name: debugging
description: Systematic debugging workflow for agent failures, MCP/tool errors, and FastAPI/runtime issues. Use when tests fail, commands error, agents misbehave, or authentication/configuration breaks.
disable-model-invocation: true
---

# Debugging

## When To Use

Cross-cutting workflow for failures in Cursor development, Strands agents, orchestrator flows, or `target-apps` services.

## Triage Workflow

1. **Reproduce**
   - Capture exact command, inputs, environment, and full error text.
   - Confirm failure is repeatable before changing code.
2. **Local configuration**
   - Verify `.env` values are present and loaded for the execution path.
   - Confirm expected model/tool identifiers are set.
3. **Integration boundaries**
   - Validate MCP server configuration, auth state, and tool availability.
   - Verify external dependencies (AWS/Redis/GitLab/Atlassian) are reachable.
4. **Runtime evidence**
   - Inspect logs, stack traces, and test output to isolate the failing layer.
   - Avoid speculative fixes without evidence.
5. **Fix and verify**
   - Apply the smallest high-confidence fix.
   - Re-run focused checks first, then broader checks if impact extends.
6. **Prevent regression**
   - Add or update tests when behavior changes or bug risk is meaningful.

## Debugging Checklist

- Confirm the issue statement is precise (actual vs expected behavior).
- Confirm reproduction steps are deterministic.
- Identify failure layer: input, business logic, integration, infrastructure, or configuration.
- Identify first bad signal (stack frame, failed assertion, HTTP status, timeout, auth rejection).
- Prefer one fix at a time to keep causality clear.
- Validate with tests and/or command evidence.

## Common Failure Patterns

1. **Auth/config errors**
   - Missing/expired tokens, wrong environment variables, invalid model IDs.
2. **MCP tool failures**
   - Server not configured, missing scopes, stale auth, unavailable tool schema.
3. **Runtime/import errors**
   - Dependency mismatch, bad module path, unhandled exception path.
4. **Queue/orchestration failures**
   - Redis unavailable, malformed payload contracts, handler mismatch.
5. **Test failures**
   - Behavior regressions, brittle assertions, fixture leakage, incorrect assumptions.

## Output Format

When reporting debugging results, use this order:

1. **Root cause** (or best current hypothesis if not fully confirmed)
2. **Evidence** (error lines, command/test output, logs)
3. **Fix applied** (or next targeted step if not fixed)
4. **Verification** (what was rerun and result)
5. **Residual risk** (if any)

If unresolved, state exactly what is blocked and the next diagnostic command to run.

## Project References

- Coding standards: [`CODING_STANDARDS.md`](../../../CODING_STANDARDS.md)
- Test quality rule: [`.cursor/rules/test-quality.mdc`](../../rules/test-quality.mdc)