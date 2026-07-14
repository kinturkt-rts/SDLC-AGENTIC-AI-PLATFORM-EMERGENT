import { MVP_TIMELINE_PHASES, PHASE_AGENT, PHASE_DISPLAY_LABEL } from './pipeline-phases';
import type { RunStatus, SdlcPhase } from '@/src/types';

export const RUN_LIVE_IDLE_MS = 60 * 60 * 1000;

export const RUN_NO_PROGRESS_IDLE_MS = 12 * 60 * 1000;

export interface ReconcileRunInput {
  status: RunStatus;
  startedAt: string;
  logMtimeMs: number;
  s3MtimeMs: number;
  logText: string | null;
  phaseDone: Record<SdlcPhase, boolean>;
  error?: string | null;
}

export interface ReconcileRunResult {
  status: RunStatus;
  currentStep: string | null;
  error?: string | null;
}

function cloudGitlabFallbackPending(log: string): boolean {
  if (/"skip_gitlab":\s*true/i.test(log)) return false;
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
      deploy: parsed.skip_gitlab === true,
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

export function mvpPipelineComplete(phaseDone: Record<SdlcPhase, boolean>): boolean {
  return MVP_TIMELINE_PHASES.every((phase) => phaseDone[phase]);
}

export function firstIncompleteMvpPhase(
  phaseDone: Record<SdlcPhase, boolean>,
): SdlcPhase | null {
  for (const phase of MVP_TIMELINE_PHASES) {
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
  for (const phase of MVP_TIMELINE_PHASES) {
    if (skipFlags[phase]) continue;
    if (!phaseDone[phase]) return phase;
  }
  return null;
}

function partialCompletionFailure(missing: SdlcPhase): ReconcileRunResult {
  const label = PHASE_DISPLAY_LABEL[missing] ?? missing;
  return {
    status: 'failed',
    currentStep: PHASE_AGENT[missing] ?? null,
    error:
      `Pipeline stopped before ${label} finished. ` +
      'Check the developer and GitLab handoffs for the failure reason.',
  };
}

/**
 * Derive truthful run status from verified evidence, not just whatever run.json / logs claim.
 *
 * Rules (in order):
 *   1. VERIFIED SUCCESS - every non-skipped required MVP phase has real artifacts →
 *      completed. This is the ONLY path to a green pipeline.
 *   2. Explicit failure signals (log/run.json) → failed.
 *   3. Claimed completion (from run.json OR a "pipeline completed" log line) that
 *      CANNOT be verified against artifacts → failed with the first missing phase named,
 *      as long as we have some evidence the run actually started in the artifact store.
 *      This is how a run that silently died mid-way stops showing as "green".
 *   4. Claimed completion with NO artifact evidence at all (very old runs whose S3
 *      lifecycle has purged everything) → trust the recorded status; we have no way to
 *      disprove it and downgrading them all to failed would be dishonest.
 *   5. Otherwise fall through to active/stalled logic.
 */
export function reconcileRunStatus(input: ReconcileRunInput): ReconcileRunResult {
  const skipFlags = parseLogSkipFlags(input.logText);
  const effectiveDone = effectivePhaseDone(input.phaseDone, skipFlags);
  const missingRequired = firstMissingRequired(input.phaseDone, skipFlags);
  const verifiedComplete = missingRequired === null;
  const hasAnyEvidence = MVP_TIMELINE_PHASES.some((p) => input.phaseDone[p]);
  const terminal = parseLogTerminalStatus(input.logText);

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

  if (input.status === 'failed' || input.status === 'cancelled') {
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
    const phase = firstIncompleteMvpPhase(effectiveDone);
    return {
      status: 'running',
      currentStep: phase ? PHASE_AGENT[phase] : null,
    };
  }

  return { status: input.status, currentStep: null };
}