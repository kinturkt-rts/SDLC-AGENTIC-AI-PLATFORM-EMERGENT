---
name: testing
description: Designs and implements tests for behavior changes with strong failure signals and coverage confidence. Use when adding or updating unit/integration tests, diagnosing missing test coverage, or validating feature changes before merge.
disable-model-invocation: true
---

# Testing

## When To Use

Apply this skill when the task includes test creation, test updates after code changes, regression prevention, or coverage improvement.

## Core Principles

- Test behavior, not implementation details.
- One path per test case; avoid branching inside a single test.
- Never place assertions behind conditionals.
- Follow AAA structure: Arrange, Act, Assert.
- Keep tests deterministic and isolated.

## Test Workflow

1. Identify the behavior change and expected outcomes.
2. Select test level:
   - `Unit`: pure logic, fast feedback.
   - `Integration`: API/database/external boundary behavior.
3. Write failing tests first when practical.
4. Implement or update code.
5. Re-run focused tests, then broader suite if change impact is larger.
6. Check for edge cases and negative paths.

## Quality Checklist

1. **Coverage alignment**: Each behavior change has at least one test.
2. **Clarity**: Test names describe expected behavior.
3. **Structure**: Arrange/Act/Assert is obvious in every test.
4. **Isolation**: No hidden dependencies on test order or shared mutable state.
5. **Assertions**: Assertions are explicit, specific, and unconditional.
6. **Edge cases**: Failure and boundary paths are covered where relevant.
7. **Maintenance**: Fixtures/factories reduce duplication without obscuring intent.

## Output Format

When reporting testing work, respond in this order:

1. **What was tested**
2. **Gaps or residual risks**
3. **Recommended next tests** (if any)

If tests were not run, explicitly state that and provide exact commands to run.

## Project References

- Test quality rule: [`.cursor/rules/test-quality.mdc`](../../rules/test-quality.mdc)
- Engineering standards: [`CODING_STANDARDS.md`](../../../CODING_STANDARDS.md)
