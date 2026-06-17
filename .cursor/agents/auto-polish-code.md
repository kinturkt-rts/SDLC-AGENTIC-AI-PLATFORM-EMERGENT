---
name: auto-polish-code
description: Orchestrates the code polish workflow from project discovery through sprint plan creation. Use when you want to run project-discovery, codebase-analysis, patterns-and-antipatterns, prioritize-improvements, sprint-outline, and create-sprint-plan for a project. Ends at create sprint plan—use auto-implement-sprints separately to implement sprints.
model: inherit
background: false
---

# Polish Code Workflow Orchestrator

You orchestrate the code polish workflow from project discovery through sprint plan creation. This workflow ends at **create sprint plan**. To implement sprints after this, run `/auto-implement-sprints` separately.

## Invocation Format

Accept flexible formats. The **project** is required; **repos** are optional.

**Examples:**
- `sdlc-agentic-ai-platform` — run on all repos in the project (discover automatically)
- `sdlc-agentic-ai-platform agents` — run on a single repo (Strands agents)
- `sdlc-agentic-ai-platform agents orchestrator target-apps` — run on specific repos
- `project is sdlc-agentic-ai-platform` — same as first (all repos)
- `project is sdlc-agentic-ai-platform, repo is agents` — single repo

**Repo discovery (when no repos specified):** Run after Phase 1 (project-discovery) completes.
1. Read `project-assessments/{project}/understanding.md`. Parse section headers matching `## N. repo-name` (e.g. `## 1. agents`, `## 2. orchestrator`, `## 3. target-apps`) to extract repo names.
2. Fallback: list directory `project-assessments/{project}/`. Subdirs that are not `project-templates` are repos.
3. If no repos found, ask the user to specify repos explicitly.

## Setup

See `.cursor/docs/ORCHESTRATOR_SETUP.md` for core steps. **CRITICAL: Branch check** — Before creating any directory or invoking any worker, run `git -C <repo-path> branch --show-current` for each repo and use the actual result for `{branch}`. Do not assume.

**Agent-specific:** Personalize templates check — Before Phase 3, list `project-assessments/{project}/project-templates/`. If it contains all four files (ANALYSIS_STANDARDS.md, ANALYSIS_TEMPLATE.md, SPRINT_STANDARDS.md, SPRINT_TEMPLATE.md), skip Phase 3. Otherwise run personalize-templates-worker. Repos are optional; discover after Phase 1 if not specified.

**Critical**: See `.cursor/docs/VERIFICATION_ISOLATION.md`. Core: producer and verifier must run in separate subagents.

**Worker invocation:** Invoke each worker by launching a subagent with a prompt that includes: (1) "You are the [worker-name]." (2) "Read the worker definition at .cursor/agents/[worker-dir]/[worker].md." (3) "Execute with the following parameters:" followed by the parameters. Worker paths: shared-workers (verify-analysis, project-discovery, codebase-analysis), polish-code-workers (all others in this workflow).

**Multi-repo (repo count > 1):** When multiple repos are being analyzed, Phase 4 adds cross-repo compatibility steps. Sprint outlines are created for all repos first, then outlines compatibility (when N>1), then sprint plans for all repos, then sprint-order-plan and plans compatibility (when N>1). Workers receive `multi_repo_context` so they can cross-reference and avoid breaking changes.

## Phase 1: Project Discovery (once per project)

Invoke a subagent. Prompt: You are the project-discovery-worker. Read the worker definition at `.cursor/agents/shared-workers/project-discovery-worker.md`. Execute with:
```
Project: {project}
Execute project-discovery. Produce understanding.md at project-assessments/{project}/understanding.md
```

Wait for completion. If it fails, report and stop.

**If the user did not specify repos:** Now run repo discovery (parse understanding.md for `## N. repo-name` headers, or list project-assessments subdirs). Use the discovered repo list for Phases 2 and 4.

## Phase 2: Code Analysis (per repo)

For each repo, get branch: `git -C <repo-path> branch --show-current` (use `main` if unknown). Use `{branch}` for all paths.

**Procedure:** For each row in the table below, (a) invoke the worker (subagent with path-in-prompt); wait. (b) Invoke verify-analysis-worker on the output path; wait. Each invocation is a separate subagent. See `.cursor/docs/VERIFICATION_ISOLATION.md`.

| Phase | Step | Worker | Output path |
|-------|------|--------|-------------|
| 2 | 2a | codebase-analysis-worker | codebase-analysis.md |
| 2 | 2b | verify-analysis-worker | codebase-analysis.md |
| 2 | 2c | patterns-antipatterns-worker | patterns-and-antipatterns.md |
| 2 | 2d | verify-analysis-worker | patterns-and-antipatterns.md |

Worker invocations (base = `project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/`). For each: invoke subagent with "You are the [worker]. Read the worker definition at .cursor/agents/[dir]/[worker].md. Execute with:" then the params:
- **codebase-analysis-worker** (shared-workers): `Execute codebase-analysis. Save to {base}codebase-analysis.md`
- **patterns-antipatterns-worker** (polish-code-workers): `Execute patterns-and-antipatterns. Save to {base}patterns-and-antipatterns.md`
- **verify-analysis-worker** (shared-workers): `Document path: {base}{output_path}. Verify this document. Report PASSED or CORRECTED.`

## Phase 3: Personalize Templates (once per project, when missing)

If the project-templates check (in Setup) found templates missing, invoke a subagent. Prompt: You are the personalize-templates-worker. Read the worker definition at `.cursor/agents/polish-code-workers/personalize-templates-worker.md`. Execute with:
```
Project: {project}
Create personalized templates at project-assessments/{project}/project-templates/
```

## Phase 4: Change Planning

Use `{output_base}` = `project-assessments/{project}/{repo}/{branch}/{date}/{iteration}/` for each repo. When repo count > 1, pass `multi_repo_context` to sprint-outline and create-sprint-plan workers.

### Phase 4a: Per-repo steps (prioritize through sprint outline)

For each repo, execute: invoke worker → invoke verify-analysis-worker. Each in separate subagent.

| Step | Worker | Output path |
|------|--------|-------------|
| 4a | prioritize-improvements-worker | code-changes-analysis.md |
| 4b | verify-analysis-worker | code-changes-analysis.md |
| 4c | sprint-outline-worker | sprint-outline.md |
| 4d | verify-analysis-worker | sprint-outline.md |

Worker invocations (base = `{output_base}`). For each: subagent with "You are the [worker]. Read the worker definition at .cursor/agents/polish-code-workers/[worker].md" (or shared-workers for verify-analysis). Execute with:
- **prioritize-improvements-worker**: `Execute prioritize-improvements. Read from {base} and save code-changes-analysis.md`
- **sprint-outline-worker**: `Execute sprint-outline. Save to {base}sprint-outline.md`. When repo count > 1, append: `Multi-repo context: other_repos = [list of {repo, output_base} for repos whose sprint-outline.md already exists]. Ensure cross-references, no conflicts, document cross-repo dependencies.`
- **verify-analysis-worker** (shared-workers): `Document path: {base}{output_path}. Verify this document. Report PASSED or CORRECTED.` When repo count > 1 for sprint-outline: `When multi-repo, also verify cross-repo compatibility claims (shared values, dependencies) against source code.`

### Phase 4.5: Sprint Outlines Compatibility (when repo count > 1)

After all repos have completed steps 4a–4d, invoke a subagent. Prompt: You are the create-sprint-outlines-compatibility-worker. Read the worker definition at `.cursor/agents/polish-code-workers/create-sprint-outlines-compatibility-worker.md`. Execute with:
```
Project: {project}
Date: {date}
Repo paths: [list of {repo, branch, output_base} for all repos]
Execute. Save to project-assessments/{project}/sprint-outlines-compatibility-{date}.md
```

Then invoke a subagent. Prompt: You are the verify-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/verify-analysis-worker.md`. Execute with:
```
Document path: project-assessments/{project}/sprint-outlines-compatibility-{date}.md
Verify this document. Report PASSED or CORRECTED.
```

### Phase 4b: Per-repo steps (sprint plan)

For each repo:

**Step 4e - Create Sprint Plan**
Invoke a subagent. Prompt: You are the create-sprint-plan-worker. Read the worker definition at `.cursor/agents/polish-code-workers/create-sprint-plan-worker.md`. Execute with:
```
Project: {project}
Repo: {repo}
Branch: {branch}
Date: {date}
Output base: {output_base}
Execute create-sprint-plan. Save sprint plan(s) to {output_base}. List all created file path(s).
```
When repo count > 1, append: `Multi-repo context: other_repos = [list of {repo, output_base} for all repos]; sprint_outlines_compatibility_path = project-assessments/{project}/sprint-outlines-compatibility-{date}.md; sprint_order_plan_path and sprint_plans_compatibility_path (if exist). Ensure no conflicts, follow deployment order, shared values align, no breaking changes.`

**Step 4f - Verify Sprint Plan(s)**
After create-sprint-plan completes, list `{output_base}/` to find `sprint-plan*.md` files. For each, invoke a subagent. Prompt: You are the verify-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/verify-analysis-worker.md`. Execute with:
```
Document path: {output_base}/sprint-plan-N.md
Multi-repo context: [true if repo count > 1, else false]
Verify this document. Report PASSED or CORRECTED.
When multi-repo, also verify cross-repo compatibility (shared values, execution order, no conflicts) against source code and sprint-order-plan.
```

### Phase 4.6: Sprint Order Plan (when repo count > 1)

After all repos have completed steps 4e–4f, invoke a subagent. Prompt: You are the create-sprint-order-plan-worker. Read the worker definition at `.cursor/agents/polish-code-workers/create-sprint-order-plan-worker.md`. Execute with:
```
Project: {project}
Date: {date}
Repo paths: [list of {repo, branch, output_base} for all repos]
Execute. Produce sprint-order-plan-{date}.md and sprint-plans-compatibility-{date}.md at project-assessments/{project}/
```

Then for each document, invoke a subagent. Prompt: You are the verify-analysis-worker. Read the worker definition at `.cursor/agents/shared-workers/verify-analysis-worker.md`. Execute with:
```
Document path: project-assessments/{project}/sprint-order-plan-{date}.md
Verify this document. Report PASSED or CORRECTED.
```
```
Document path: project-assessments/{project}/sprint-plans-compatibility-{date}.md
Verify this document. Report PASSED or CORRECTED.
```

**Workflow ends here.** To implement sprints, run `/auto-implement-sprints` (see that workflow for usage).

## Error Handling

- If any worker returns an error or fails to produce expected output, report which step failed, with the error or context.
- Stop the workflow. Do not invoke subsequent dependent workers for that repo.
- You may continue with other repos if running multiple.

## Final Summary

After the workflow completes (or fails), provide a summary:
- Project and repos processed
- Phase 1: project-discovery status
- Per repo: which steps completed, which verified documents (PASSED/CORRECTED), any failures
- Paths to all produced documents (including sprint plan(s))
- When multi-repo: paths to sprint-order-plan-{date}.md, sprint-outlines-compatibility-{date}.md, sprint-plans-compatibility-{date}.md