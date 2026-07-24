import { COMPLETION_PHASES, PHASE_AGENT, PHASE_DISPLAY_LABEL } from './pipeline-phases';
import type { RunStatus, SdlcPhase } from '@/src/types';

export const RUN_LIVE_IDLE_MS = 60 * 60 * 1000;

export const RUN_NO_PROGRESS_IDLE_MS = 12 * 60 * 1000;

/** Pipeline agent order used to prefer the furthest live step when sources disagree. */
const AGENT_PROGRESS_ORDER = [
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'gitlab-agent',
  'qa-agent',
  'security-agent',
  'devops-agent',
] as const;

export interface ReconcileRunInput {
  status: RunStatus;
  startedAt: string;
  logMtimeMs: number;
  s3MtimeMs: number;
  logText: string | null;
  phaseDone: Record<SdlcPhase, boolean>;
  error?: string | null;
  /** From run.json / log markers — used when artifact index lags behind live progress. */
  reportedCurrentStep?: string | null;
}

function furthestAgentStep(a: string | null | undefined, b: string | null | undefined): string | null {
  if (!a) return b ?? null;
  if (!b) return a;
  const ai = AGENT_PROGRESS_ORDER.indexOf(a as (typeof AGENT_PROGRESS_ORDER)[number]);
  const bi = AGENT_PROGRESS_ORDER.indexOf(b as (typeof AGENT_PROGRESS_ORDER)[number]);
  if (ai < 0) return b;
  if (bi < 0) return a;
  return ai >= bi ? a : b;
}

export interface ReconcileRunResult {
  status: RunStatus;
  currentStep: string | null;
  error?: string | null;
}

function cloudGitlabFallbackPending(log: string): boolean {
  if (/"skip_gitlab":\s*true/i.test(log)) return false;
  if (
    /\[status-poll\]\s+status:\s*(failed|cancelled)\b/i.test(log) ||
    /sdlc pipeline failed/i.test(log) ||
    /developer-agent failed/i.test(log)
  ) {
    return false;
  }
  if (!/--- gitlab ---/i.test(log)) return true;
  return !(
    /\[gitlab-fallback\]\s+cloud gitlab-agent succeeded/i.test(log) ||
    /\[gitlab\]\s+handoff already exists/i.test(log) ||
    /\[gitlab-fallback\].*failed or no handoff/i.test(log)
  );
}

export function parseLogTerminalStatus(
  log: string | null,
): { status: 'completed' | 'failed'; error?: string } | null {
  if (!log?.trim()) return null;
  const lower = log.toLowerCase();

  const orchestratorStatusSuccess = log.split('\n').some((line) => {
    const trimmed = line.trim();
    if (/^\[gitlab-fallback\]/i.test(trimmed)) return false;
    return /^status:\s*success\b/i.test(trimmed);
  });

  if (
    lower.includes('sdlc pipeline completed') ||
    /\[gitlab\]\s+handoff already exists/i.test(log) ||
    /\[gitlab-fallback\]\s+cloud gitlab-agent succeeded/i.test(log)
  ) {
    return { status: 'completed' };
  }

  if (/\[cloud-invoke\]\s+failed/i.test(log)) {
    return { status: 'failed', error: 'Cloud orchestrator invoke failed' };
  }

  if (
    /\[gitlab-fallback\]\s+developer-agent did not reach a completed handoff/i.test(log) ||
    /\[dev-fallback\]\s+handoff status after wait:\s*not completed/i.test(log)
  ) {
    return {
      status: 'failed',
      error: 'developer-agent did not reach a completed handoff after retries',
    };
  }

  const errLine = log
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l.toLowerCase().startsWith('error:'));
  if (errLine) {
    if (cloudGitlabFallbackPending(log)) return null;
    return { status: 'failed', error: errLine.replace(/^error:\s*/i, '') };
  }

  if (lower.includes('sdlc pipeline failed')) {
    return { status: 'failed', error: 'SDLC pipeline failed' };
  }
  if (/\bstatus:\s*(error|failed)\b/i.test(log)) {
    if (cloudGitlabFallbackPending(log)) return null;
    return { status: 'failed', error: 'Orchestrator invoke failed' };
  }
  if (/\bfailed \(exit \d+\)/i.test(log) || lower.includes('traceback (most recent call last)')) {
    return { status: 'failed', error: 'Smoke script failed' };
  }

  return null;
}

export function parseLogSkipFlags(
  log: string | null,
): Partial<Record<SdlcPhase, boolean>> {
  if (!log) return {};
  const match = log.match(/\{[\s\S]*?"skip_[a-z]+"[\s\S]*?\}/);
  if (!match) return {};

  try {
    const parsed = JSON.parse(match[0]) as Record<string, unknown>;
    return {
      requirements: parsed.skip_product === true,
      architecture: parsed.skip_architect === true,
      data: parsed.skip_db === true,
      implementation: parsed.skip_developer === true,
      publish: parsed.skip_gitlab === true,
      deploy: parsed.skip_devops === true,
      qa: parsed.skip_verify === true,
    };
  } catch {
    return {};
  }
}

export function lastRunActivityMs(input: {
  startedAt: string;
  logMtimeMs: number;
  s3MtimeMs: number;
}): number {
  const started = Date.parse(input.startedAt);
  return Math.max(
    Number.isFinite(started) ? started : 0,
    input.logMtimeMs || 0,
    input.s3MtimeMs || 0,
  );
}

export function pipelineComplete(phaseDone: Record<SdlcPhase, boolean>): boolean {
  return COMPLETION_PHASES.every((phase) => phaseDone[phase]);
}

export function firstIncompletePhase(
  phaseDone: Record<SdlcPhase, boolean>,
): SdlcPhase | null {
  for (const phase of COMPLETION_PHASES) {
    if (!phaseDone[phase]) return phase;
  }
  return null;
}

/** Compute effective phaseDone honoring parsed skip flags. */
function effectivePhaseDone(
  phaseDone: Record<SdlcPhase, boolean>,
  skipFlags: Partial<Record<SdlcPhase, boolean>>,
): Record<SdlcPhase, boolean> {
  const out = { ...phaseDone };
  for (const key of Object.keys(skipFlags) as SdlcPhase[]) {
    if (skipFlags[key]) out[key] = true;
  }
  return out;
}

function firstMissingRequired(
  phaseDone: Record<SdlcPhase, boolean>,
  skipFlags: Partial<Record<SdlcPhase, boolean>>,
): SdlcPhase | null {
  for (const phase of COMPLETION_PHASES) {
    if (skipFlags[phase]) continue;
    if (!phaseDone[phase]) return phase;
  }
  return null;
}

function partialCompletionFailure(missing: SdlcPhase): ReconcileRunResult {
  const label = PHASE_DISPLAY_LABEL[missing] ?? missing;
  const agent = PHASE_AGENT[missing];
  let error = `Pipeline stopped before ${label} finished.`;
  if (missing === 'implementation') {
    error =
      'Developer-agent did not complete successfully. Open the run and check the developer handoff for the concrete error.';
  } else if (missing === 'publish') {
    error =
      'GitLab publish did not complete successfully. Open the run and check the GitLab handoff for the concrete error.';
  } else if (missing === 'deploy') {
    error =
      'AWS deploy did not complete successfully. Open the run and check the DevOps handoff for the concrete error.';
  } else if (agent) {
    error = `Pipeline stopped before ${label} finished (${agent}).`;
  }
  return {
    status: 'failed',
    currentStep: agent ?? null,
    error,
  };
}

export function reconcileRunStatus(input: ReconcileRunInput): ReconcileRunResult {
  const skipFlags = parseLogSkipFlags(input.logText);
  const effectiveDone = effectivePhaseDone(input.phaseDone, skipFlags);
  const missingRequired = firstMissingRequired(input.phaseDone, skipFlags);
  const verifiedComplete = missingRequired === null;
  const hasAnyEvidence = COMPLETION_PHASES.some((p) => input.phaseDone[p]);
  const terminal = parseLogTerminalStatus(input.logText);

  if (input.status === 'cancelled') {
    return {
      status: 'cancelled',
      currentStep: null,
      error: input.error ?? undefined,
    };
  }

  if (verifiedComplete) {
    return { status: 'completed', currentStep: null };
  }

  if (terminal?.status === 'failed') {
    return {
      status: 'failed',
      currentStep: null,
      error: terminal.error ?? input.error ?? 'Pipeline failed',
    };
  }

  if (input.status === 'failed') {
    return {
      status: input.status,
      currentStep: null,
      error: input.error ?? undefined,
    };
  }

  const claimsCompleted = input.status === 'completed' || terminal?.status === 'completed';
  if (claimsCompleted) {
    // Claimed completion but at least one required phase is unverifiable.
    // If there is *any* evidence in the artifact store for this run, the pipeline
    // clearly ran but didn't finish → mark it failed with the missing phase named.
    // If there is no evidence at all (old run, artifacts pruned), trust run.json.
    if (hasAnyEvidence && missingRequired) {
      return partialCompletionFailure(missingRequired);
    }
    return { status: 'completed', currentStep: null };
  }

  const idleMs = Date.now() - lastRunActivityMs(input);
  const isActiveStatus = input.status === 'running' || input.status === 'queued';
  const anyProgress = hasAnyEvidence;
  const idleThresholdMs = anyProgress ? RUN_LIVE_IDLE_MS : RUN_NO_PROGRESS_IDLE_MS;

  if (isActiveStatus && idleMs > idleThresholdMs) {
    return {
      status: 'failed',
      currentStep: null,
      error: anyProgress
        ? 'Pipeline stalled (no activity in the last hour)'
        : 'Pipeline abandoned (no activity since it started - never completed product-agent)',
    };
  }

  if (isActiveStatus) {
    const phase = firstIncompletePhase(effectiveDone);
    const fromArtifacts = phase ? PHASE_AGENT[phase] : null;
    return {
      status: 'running',
      currentStep: furthestAgentStep(fromArtifacts, input.reportedCurrentStep),
    };
  }

  return { status: input.status, currentStep: null };
}