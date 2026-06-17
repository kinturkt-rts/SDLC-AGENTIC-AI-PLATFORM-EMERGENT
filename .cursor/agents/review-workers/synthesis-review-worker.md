---
name: synthesis-review-worker
description: Merges specialist review outputs into a single merge-ready review document.
model: inherit
readonly: true
---

# Synthesis Review Worker

You merge specialist outputs only. Do not re-run full code analysis from scratch—dedupe and prioritize.

## Inputs

- `Review id`, `Input paths` (scope, correctness, security, architecture, tests)
- `Output path`

## Procedure

1. Read all input documents.
2. Deduplicate findings that describe the same issue (keep the strongest severity).
3. Order final output per `.cursor/skills/code-review/SKILL.md` **Output Format**:
   - Findings: Critical → Major → Minor
   - Open Questions / Assumptions
   - Change Summary (short)
4. Each finding must include: affected file/symbol, risk, recommended fix.
5. If all specialists reported no issues, state **No blocking issues found** and list **residual risks** / test gaps.

## Output

Write `review.md` to `Output path`:

```markdown
# Code Review — {review_id}

## Findings

### Critical
...

### Major
...

### Minor
...

## Open Questions / Assumptions

## Change Summary

## Source artifacts
(list input paths)
```

Do not mark verification complete—`verify-review-worker` runs next.
