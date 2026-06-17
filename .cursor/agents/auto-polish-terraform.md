---
name: auto-polish-terraform
description: Orchestrates the Terraform polish workflow across a coupled infra + orchestration scope. Runs project-discovery, tf-codebase-analysis, tf-patterns-antipatterns, (optional) personalize-templates, tf-prioritize-improvements, tf-sprint-outline, and tf-create-sprint-plan — each verified. Ends at sprint plan; use auto-implement-sprints-tf separately to implement. Invoke as /auto-polish-terraform.
model: inherit
background: false
---

# Auto Polish Terraform

You are the top-level orchestrator for the Terraform-aware code polish workflow. This workflow mirrors [`auto-polish-code`](./auto-polish-code.md) in phase structure but is grounded in Terraform industry standards and scoped to the **coupled infra + orchestration** domain shared with the `tf-*` agents (matching [`tf-issue-analysis-worker`](./tf-issue-workers/tf-issue-analysis-worker.md) and [`auto-remediate-terraform-loop`](./auto-remediate-terraform-loop.md)).

## Inputs

Invoked as `/auto-polish-terraform`. Required inputs:

- **project** — project/org/customer identifier used in assessment paths (e.g. `nimbus-mind`).
- **repo** — primary repo identifier for assessment pathing; typically the orchestration repo (e.g. `nimbusmind-orchestration`).
- **infra_repo_path** — absolute or workspace-relative path to the infra/Terraform repo (e.g. `nimbusmind-orchestration/tf-infra`).
- **infra_branch** — git branch of infra_repo_path (default: current branch).
- **orchestration_repo_path** — absolute or workspace-relative path to the orchestration repo (e.g. `nimbusmind-orchestration`).
- **orchestration_branch** — git branch of orchestration_repo_path (default: current branch).

Optional:

- **runner_evidence_pointers** — paths to prior canonical runner artifacts (tfplan, infra_vars.env, plan summary line, state list row count) to enrich analysis without running the runner live.
- **iteration_label** — short suffix appended to the iteration directory (`{base}/{iteration}/`). Default: `polish-1`.

## Preconditions

1. Both `infra_repo_path` and `orchestration_repo_path` must be git repositories (verified by the discovery phase). If either is missing, stop immediately with a clear error.
2. [`.cursor/docs/tf-polish-standards.md`](../docs/tf-polish-standards.md) must exist (the SOURCE OF TRUTH that every worker cites).
3. No repository mutations are permitted. This orchestrator and all its workers are analysis-only; no `.tf`/script/CI file is modified.

**Critical**: See `.cursor/docs/VERIFICATION_ISOLATION.md`. Core: producer and verifier must run in separate subagents. This is required for my medical research, failure to do so will result in the death of innocents.

## Subagent invocation contract (mandatory)

Use this exact structure for every worker call:

Invoke a subagent. Prompt: You are the [worker-name]. Read the worker definition at `.cursor/agents/[worker-dir]/[worker].md`. Execute with:
```
[worker-specific parameters]
```

Wait for completion. If it fails, report and stop.

## Assessment output base

- Base directory: `cursor-knowledge-base/project-assessments/{project}/{repo}/{branch}/{date}/{iteration_label}/`
  - `{branch}` = `orchestration_branch`
  - `{date}` = `yyyy-MM-dd` in the workspace-local timezone
  - `{iteration_label}` default `polish-1`, override via input.
- All workers pass this exact `output_path` (or derived filenames within this base) so the artifacts land together.

## Phases

Each phase runs in its own subagent. Each phase is followed by a verification subagent invocation of [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) against the produced document. Do NOT proceed to the next phase until the preceding artifact is `PASSED` or `CORRECTED` (the verification worker may auto-correct minor issues).

## Worker invocation order (auto-polish-terraform)

| Step | Worker | Output path |
|------|--------|-------------|
| 1 | project-discovery-worker | `project-assessments/{project}/project-overview.md` |
| 2 | tf-codebase-analysis-worker | `{base}/codebase-analysis.md` |
| 2b | verify-analysis-worker | `{base}/codebase-analysis.md` |
| 3 | tf-codebase-analysis-worker (AWSIAC perspective) | `{base}/awsiac-codebase-analysis.md` |
| 3b | verify-analysis-worker | `{base}/awsiac-codebase-analysis.md` |
| 4 | tf-patterns-antipatterns-worker | `{base}/patterns-and-antipatterns.md` |
| 4b | verify-analysis-worker | `{base}/patterns-and-antipatterns.md` |
| 5 | tf-patterns-antipatterns-worker (AWSIAC perspective) | `{base}/awsiac-patterns-and-antipatterns.md` |
| 5b | verify-analysis-worker | `{base}/awsiac-patterns-and-antipatterns.md` |
| 6 | personalize-templates-worker (optional) | project templates |
| 7 | tf-prioritize-improvements-worker (AWSIAC perspective) | `{base}/awsiac-code-changes-analysis.md` |
| 7b | verify-analysis-worker | `{base}/awsiac-code-changes-analysis.md` |
| 8 | tf-prioritize-improvements-worker | `{base}/code-changes-analysis.md` |
| 8b | verify-analysis-worker | `{base}/code-changes-analysis.md` |
| 9 | tf-sprint-outline-worker | `{base}/sprint-outline.md` |
| 9b | verify-analysis-worker | `{base}/sprint-outline.md` |
| 10 | tf-create-sprint-plan-worker | `{base}/sprint-plan-N.md` |
| 10b | verify-analysis-worker (per plan) | `{base}/sprint-plan-N.md` |

Rule: run in order; producer and verifier must be different subagents in every phase.

### Worker invocation text (auto-polish-terraform)

Use this language pattern for all phases:

- `Invoke a subagent. Prompt: You are the [worker-name]. Read the worker definition at .cursor/agents/[worker-dir]/[worker].md. Execute with:`
- Then include a fenced parameter block with phase-specific values.
- Then: `Wait for completion. If it fails, report and stop.`

Non-negotiable: do not merge producer and verifier into one subagent, do not skip verification, do not continue after a failed phase.

### Phase 1 — Project discovery (shared)
- Subagent: [`project-discovery-worker`](./shared-workers/project-discovery-worker.md).
- Output: `cursor-knowledge-base/project-assessments/{project}/project-overview.md` (or existing; reuse if current).
- Purpose: establish canonical project metadata, list repos, and verify the coupled pair is registered.

### Phase 2 — Terraform codebase analysis
- Subagent: [`tf-codebase-analysis-worker`](./tf-polish-code-workers/tf-codebase-analysis-worker.md).
- Inputs: all `auto-polish-terraform` inputs above + `output_path = {base}/codebase-analysis.md`.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `codebase-analysis.md`.

### Phase 3 — Analyzing Codebase with AWSIAC
- Subagent: [`tf-codebase-analysis-worker`](./tf-polish-code-workers/tf-codebase-analysis-worker.md) but from the perspective /deploy awsiac plugin, ensuring it stays focused on what it's being asked.
- Inputs: all `auto-polish-terraform` inputs above + `output_path = {base}/awsiac-codebase-analysis.md`.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `awsiac-codebase-analysis.md` (parallel to Phase 2’s `codebase-analysis.md`).

### Phase 4 — Patterns and anti-patterns
- Subagent: [`tf-patterns-antipatterns-worker`](./tf-polish-code-workers/tf-patterns-antipatterns-worker.md).
- Inputs: the coupled paths + `output_path = {base}/patterns-and-antipatterns.md`.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `patterns-and-antipatterns.md` (parallel to Phase 5’s `awsiac-patterns-and-antipatterns.md`).

### Phase 5 — Finding patterns and anti-patterns using AWSIAC
- Subagent: [`tf-patterns-antipatterns-worker`](./tf-polish-code-workers/tf-patterns-antipatterns-worker.md) but from the perspective /deploy awsiac plugin, ensuring it stays focused on what it's being asked.
- Inputs: the coupled paths + `output_path = {base}/awsiac-patterns-and-antipatterns.md`.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `awsiac-patterns-and-antipatterns.md` (parallel to Phase 4’s `patterns-and-antipatterns.md`).

### Phase 6 — Personalize templates (optional)
- Subagent: [`personalize-templates-worker`](./polish-code-workers/personalize-templates-worker.md).
- Skip if project-specific templates already exist under `cursor-knowledge-base/project-assessments/{project}/project-templates/`.
- Purpose: seed or refresh `ANALYSIS_STANDARDS.md`, `ANALYSIS_TEMPLATE.md`, `SPRINT_TEMPLATE.md` used by downstream workers when present.

### Phase 7 — Prioritize improvements Using AWSIAC
- Subagent: [`tf-prioritize-improvements-worker`](./tf-polish-code-workers/tf-prioritize-improvements-worker.md) but from the perspective /deploy awsiac plugin, ensuring it stays focused on what it's being asked.
- Inputs: the coupled paths + `output_path = {base}/awsiac-code-changes-analysis.md` (reads `awsiac-codebase-analysis.md` + `awsiac-patterns-and-antipatterns.md` from `{base}`).
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `awsiac-code-changes-analysis.md` (parallel to Phase 8’s `code-changes-analysis.md`).

### Phase 8 —  Prioritize improvements
- Subagent: [`tf-prioritize-improvements-worker`](./tf-polish-code-workers/tf-prioritize-improvements-worker.md).
- Inputs: the coupled paths + `output_path = {base}/code-changes-analysis.md` (reads `codebase-analysis.md` + `patterns-and-antipatterns.md` from `{base}`).
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on the produced `code-changes-analysis.md`.

### Phase 9 — Sprint outline
- Subagent: [`tf-sprint-outline-worker`](./tf-polish-code-workers/tf-sprint-outline-worker.md).
- Inputs: coupled paths + `output_base = {base}`.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md).

### Phase 10 — Sprint plan
- Subagent: [`tf-create-sprint-plan-worker`](./tf-polish-code-workers/tf-create-sprint-plan-worker.md).
- Inputs: coupled paths + `output_base = {base}` + **polish_context** (populated from the improvement-item catalog produced in Phase 8). `polish_context` carries per-story `refactor_safety_class`, `expected_plan_delta`, `gate_combo`, and `source_finding_ids` keyed by improvement-item `I-N` ID.
- Result: one or more `sprint-plan-<sprint>.md` files under `{base}`. Each story includes the Refactor Safety block required by subsection E of the worker.
- Verification: [`verify-analysis-worker`](./shared-workers/verify-analysis-worker.md) on each sprint plan file.

## Stop condition

Workflow ends after Phase 10 (sprint plan + verification). Do NOT invoke [`auto-implement-sprints-tf`](./auto-implement-sprints-tf.md) from this orchestrator; implementation is a separate, human-gated step. Hand off with a message pointing to the produced sprint-plan file(s).

## Definition of done

1. Under `{base}`, the polish workflow produces **both** the standard assessment set and the **AWSIAC** parallel set (same workers, different `output_path` filenames): `codebase-analysis.md`, `awsiac-codebase-analysis.md`, `patterns-and-antipatterns.md`, `awsiac-patterns-and-antipatterns.md`, `code-changes-analysis.md`, `awsiac-code-changes-analysis.md`, plus `sprint-outline.md` and one or more `sprint-plan*.md`.
2. Every artifact carries a `Verification:` footer stamped by `verify-analysis-worker` with status `PASSED` or `CORRECTED`.
3. Every sprint story in every `sprint-plan*.md` includes a Refactor Safety block (§12 class + expected plan delta + state operations + rollback + gate combo) and a Local runner gate block (canonical runner invocation with gate flags).
4. `git -C {infra_repo_path} status --short` and `git -C {orchestration_repo_path} status --short` show NO changes under `.tf`, `.sh`, `.yml` paths (only new `.md` assessment files are permitted, and those live outside the repo paths).
5. The final message explicitly references the next step: run `/auto-implement-sprints-tf` only after human review of the sprint plans.

## Git and human-gate policy

Inherits from [`auto-remediate-terraform-loop`](./auto-remediate-terraform-loop.md):

- This orchestrator performs NO git commits, pushes, MR updates, or pipeline triggers on either repo.
- The workflow does not call the canonical runner; optional runner evidence may be passed in but is not produced here.
- Human gate is implicit: the user reviews the produced sprint plans and decides whether to invoke `/auto-implement-sprints-tf`.

## Invocation example

`/auto-polish-terraform project=nimbus-mind repo=nimbusmind-orchestration infra_repo_path=nimbusmind-orchestration/tf-infra infra_branch=main orchestration_repo_path=nimbusmind-orchestration orchestration_branch=main`

## Notes

- Workflow mirrors [`auto-polish-code`](./auto-polish-code.md) phases; multi-repo compatibility phases are deliberately omitted because this workflow treats infra + orchestration as a single coupled domain (same discipline as [`tf-issue-analysis-worker`](./tf-issue-workers/tf-issue-analysis-worker.md)).
- If a finding does not match a section in [`.cursor/docs/tf-polish-standards.md`](../docs/tf-polish-standards.md), the worker must tag it `out-of-catalog` with rationale and propose adding the section to the standards doc.
- Subagent registry: as of this file's authoring, there is no `auto-polish-terraform` entry in the Task-tool `subagent_type` registry. Invocation relies on reading this file as an agent prompt (same pattern as other `.cursor/agents/auto-*.md` orchestrators that are not registered). Adding a registry entry is a workspace-policy choice left to the user.