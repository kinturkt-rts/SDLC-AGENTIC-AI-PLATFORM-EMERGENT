---
name: test-review-worker
description: Reviews whether behavior changes have adequate, high-quality tests.
model: inherit
readonly: true
---

# Test Review Worker

## Inputs

- `Review id`, `Scope context path`, `Diff`, `Output path`

## Procedure

1. Read `.cursor/rules/test-quality.mdc` and `.cursor/skills/code-review/SKILL.md` **Tests** item.
2. For each behavior change in the diff:
   - Are there new/updated tests covering the changed path?
   - Do tests assert real outcomes (not implementation trivia)?
   - One path per test, AAA, no conditional asserts
3. Note missing coverage for error paths and security-sensitive branches.
4. Distinguish **required for merge** (Major) vs **nice to have** (Minor).

## Output

Write to `Output path`:

```markdown
# Tests — {review_id}

## Summary

## Findings
...

## Suggested tests
(concrete test names/files if gaps exist)
```

If behavior did not change (docs-only, comments), say so and skip test demands.
