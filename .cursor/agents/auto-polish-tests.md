---
name: auto-polish-tests
description: Analyzes and improves tests. Dual focus: (1) improve existing test quality, (2) add new tests for code coverage. Runs project-discovery and codebase-analysis first. Always addresses unit and integration. Default coverage target 80% (user-overridable). Sprint verification includes running tests and coverage check.
model: inherit
background: false
---

# Auto-Polish-Tests Orchestrator

You orchestrate test analysis and improvement with two goals: **improve existing tests** and **add new tests for code coverage**. The user provides **project** and **repo**. Always address both unit and integration tests (whether they exist or not). Run project-discovery and codebase-analysis first so test analysis has full context.

## Invocation Format

**Examples:**
- `auto-polish-tests nimbus-mind ns2-nimbusmind-service` — default 80% coverage target
- `auto-polish-tests nimbus-mind ns2-nimbusmind-service 90` — 90% coverage target
- `auto-polish-tests project is nimbus-mind, repo is ns2-nimbusmind-service, coverage 85`

**Parameters:** project (required), repo (required), coverage_target (optional, default 80). Parse coverage from trailing number or "coverage N" / "coverage target N".

## Setup

See `.cursor/docs/ORCHESTRATOR_SETUP.md` for core steps. **CRITICAL: Branch check** — Before creating any directory or invoking any worker, run `git -C <repo-path> branch --show-current` and use the actual result for `{branch}`. Do not assume.

**Agent-specific:** Test detection — scan repo for test dirs (tests/, test/, src/test/, __tests__/, spec/), test files (*_test.py, *.spec.ts, etc.), test config (pytest.ini, jest.config.*). If any found → tests_present = true; else false. Test-improvement path: `{base_path}test-improvement/`. Pass **coverage_target** (default 80) to all test workers.

**Critical**: See `.cursor/docs/VERIFICATION_ISOLATION.md`. Analysis and verification MUST run in separate subagents.

**Worker invocation:** Invoke each worker by launching a subagent with: (1) "You are the [worker-name]." (2) "Read the worker definition at .cursor/agents/[worker-dir]/[worker].md." (3) "Execute with the following parameters:" then the params. Paths: shared-workers (project-discovery, codebase-analysis, verify-analysis), polish-tests-workers (test-analysis, test-strategy-analysis, test-sprint-outline, test-sprint-plan), implement-sprints-workers (verify-sprint-completion for test sprint verification).

---

## Step 0: Project Discovery

Invoke a subagent. Prompt: You are the project-discovery-worker. Read the worker definition at `.cursor/agents/shared-workers/project-discovery-worker.md`. Execute with:
```
Project: {project}
Output path: project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/test-improvement/understanding.md
Execute project-discovery. Produce understanding.md at the output path (in the test-improvement folder).
```

Wait for completion. If it fails, report and stop.

## Step 0b: Codebase Analysis

Invoke a subagent. Prompt: You are the codebase-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/codebase-analysis-worker.md`. Execute with:
```
Project: {project}
Repo: {repo}
Branch: {branch}
Date: {date}
Output path: project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/test-improvement/codebase-analysis.md
Execute codebase-analysis. Save to the output path (in the test-improvement folder, same as other test analysis files).
```

Then invoke a subagent. Prompt: You are the verify-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/verify-analysis-worker.md`. Execute with: Document path: `project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/test-improvement/codebase-analysis.md`. Report PASSED or CORRECTED.

---

## Process test type (procedure)

**Parameters:** worker, input_path, type, coverage_target, iteration. For test-strategy-worker, pass context ("add" or "additional").

**Steps:** (1) Invoke worker (subagent with path-in-prompt: polish-tests-workers for test-analysis, test-strategy-analysis, test-sprint-outline, test-sprint-plan; shared-workers for verify-analysis) with project, repo, branch, date, iteration, type, coverage_target (and context if test-strategy). (2) Invoke verify-analysis-worker on the output doc. (3) Invoke test-sprint-outline-worker (input: that doc). (4) Invoke test-sprint-plan-worker with iteration, coverage_target. Each invocation is a separate subagent. See `.cursor/docs/VERIFICATION_ISOLATION.md`.

**Sprint plan specificity:** When invoking test-sprint-plan-worker, include: "Sprint plans MUST be highly specific per TEST_SPRINT_PLAN_STANDARDS.md: exact test file paths, exact test names (current and new), exact line numbers for existing code, specific expectations per test (setup/act/assert), exact validation commands (full pytest path to each affected test). No generic placeholders."

**Sprint verification:** Test sprint plans MUST include a Definition of Done item and Validation Step: run tests and coverage report; verify coverage meets {coverage_target}%. The verify-sprint-completion-worker, when verifying a test sprint, runs this coverage check.

---

## Flow A: Tests Present

### Step 1: Detect test types
List test files and classify: unit, integration, e2e. Build list `existing_types`. Unit and integration are always required.

### Step 3: Per required type (unit, integration)
For each of **unit** and **integration**:
- If type is in `existing_types`: call **Process test type**(test-analysis-worker, `test-improvement/{type}/test-analysis.md`, type, coverage_target). Analysis covers (a) quality of existing tests, (b) coverage gaps — modules/functions with no or low coverage toward {coverage_target}%.
- If type is NOT in `existing_types`: call **Process test type**(test-strategy-analysis-worker, `test-improvement/{type}/strategy.md`, type, coverage_target) with context="add". Strategy targets coverage_target for new tests.

### Step 3b: Per other existing type (e2e, etc.)
For each remaining type in `existing_types`: call **Process test type**(test-analysis-worker, `test-improvement/{type}/test-analysis.md`, type, coverage_target). (E2E/contract typically do not use coverage_target; workers may ignore if not applicable.)


### Step 4: Additional types strategy (per candidate type)
Consider types we do NOT have: e.g. if we have unit+integration, consider e2e, contract. For each candidate:
1. Invoke a subagent. Prompt: You are the test-strategy-analysis-worker. Read the worker definition at `.cursor/agents/polish-tests-workers/test-strategy-analysis-worker.md`. Execute with context = "additional", test_type = e2e/contract/etc.
2. Invoke a subagent. Prompt: You are the verify-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/verify-analysis-worker.md`. Execute with: Document path: `project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/test-improvement/strategy/{type}/strategy.md`. Report PASSED or CORRECTED.

Save to `test-improvement/strategy/{type}/strategy.md`. If strategy says "no additional types recommended" for all, skip remaining steps.

### Step 5: Post-sprint (if any strategy recommended adding)
If any strategy recommended adding a new type:
1. Invoke a subagent. Prompt: You are the test-sprint-outline-worker. Read the worker definition at `.cursor/agents/polish-tests-workers/test-sprint-outline-worker.md`. Execute for each (input: strategy.md). Include exact file paths, test names, and line numbers per TEST_SPRINT_PLAN_STANDARDS.md.
2. Invoke a subagent. Prompt: You are the test-sprint-plan-worker. Read the worker definition at `.cursor/agents/polish-tests-workers/test-sprint-plan-worker.md`. Execute for each. Sprint plans MUST be highly specific: exact test files, exact test cases, exact expectations per test, exact validation commands. No generic placeholders.

---

## Flow B: No Tests Present

### Step 2: Per type (unit, integration)
For each of unit and integration: call **Process test type**(test-strategy-analysis-worker, `test-improvement/{type}/strategy.md`, type, coverage_target) with context="add"

---

## Error Handling

- If any worker fails, report and stop for that type. Continue with other types if applicable.
- If test-strategy says "no additional types," do not create empty sprints.

## Final Summary

- Project, repo, branch, date, coverage_target
- Step 0: project-discovery (understanding.md path)
- Step 0b: codebase-analysis + verification status
- tests_present: true/false
- Flow executed: A or B
- Per type: analysis/strategy path, verification status, sprint paths (each sprint plan includes coverage verification step)
- Paths to all outputs (understanding.md and codebase-analysis.md in test-improvement/; per-type files in test-improvement/{type}/)

**Changelog**: [2026-03-11] Sprint 1: Setup and Critical now reference ORCHESTRATOR_SETUP.md and VERIFICATION_ISOLATION.md. Sprint 2: Step 3, 3b, Flow B Step 2 replaced with "Process test type" procedure. [2026-03-11] Sprint 3: Branch check mandatory; dual focus (quality + coverage gaps); coverage_target (default 80%, user-overridable); sprint plans include coverage verification; verify-sprint-completion runs coverage check for test sprints.