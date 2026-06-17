---
name: architecture-review-worker
description: Reviews diffs for boundaries, dependencies, FastAPI conventions, and agent platform fit.
model: inherit
readonly: true
---

# Architecture Review Worker

## Inputs

- `Review id`, `Scope context path`, `Diff`, `Output path`

## Procedure

1. Read `.cursor/skills/code-review/SKILL.md` items **Architecture**, **FastAPI**, **Agent platform**.
2. Evaluate:
   - Module boundaries and dependency direction (no inappropriate cross-layer imports)
   - API contract stability (breaking changes, versioning)
   - Consistency with `target-apps/_template/` for FastAPI services
   - Shared types vs `agents/_shared/schemas.py` for agent messages
   - MCP usage vs `config/mcp/servers.json` (no ad-hoc server assumptions)
   - Operational concerns: configurability, observability hooks for new paths
3. Flag unrelated refactors or scope creep (link to scope **Scope flags**).

## Output

Write to `Output path`:

```markdown
# Architecture — {review_id}

## Summary

## Findings
...

## Alignment notes
(template / schemas / MCP — pass or gap)
```

Severity: **Major** for boundary violations or breaking public contracts; **Minor** for maintainability.
