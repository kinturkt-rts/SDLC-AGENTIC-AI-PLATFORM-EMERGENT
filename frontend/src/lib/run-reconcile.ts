import { MVP_TIMELINE_PHASES, PHASE_AGENT } from './pipeline-phases';
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
    orchestratorStatusSuccess ||
    /\[apply-rds-local\]\s+ok\b/i.test(log) ||
    /\[gitlab\]\s+handoff already exists/i.test(log) ||
    /\[gitlab-fallback\]\s+cloud gitlab-agent succeeded/i.test(log)
  ) {
    return { status: 'completed' };
  }

  if (/\[cloud-invoke\]\s+failed/i.test(log)) {
    return { status: 'failed', error: 'Cloud orchestrator invoke failed' };
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

/** Derive truthful run status from logs, S3 artifacts, and last activity - not stale run.json alone. */
export function reconcileRunStatus(input: ReconcileRunInput): ReconcileRunResult {
  const terminal = parseLogTerminalStatus(input.logText);
  if (terminal?.status === 'completed') {
    return { status: 'completed', currentStep: null };
  }

  if (mvpPipelineComplete(input.phaseDone)) {
    const skipGitlab = parseLogSkipFlags(input.logText).deploy === true;
    if (skipGitlab || input.phaseDone.deploy) {
      return { status: 'completed', currentStep: null };
    }
  }

  if (terminal?.status === 'failed') {
    return {
      status: 'failed',
      currentStep: null,
      error: terminal.error ?? input.error ?? 'Pipeline failed',
    };
  }

  if (input.status === 'completed' || input.status === 'failed' || input.status === 'cancelled') {
    return {
      status: input.status,
      currentStep: null,
      error: input.error ?? undefined,
    };
  }

  const idleMs = Date.now() - lastRunActivityMs(input);
  const isActiveStatus = input.status === 'running' || input.status === 'queued';
  const anyProgress = MVP_TIMELINE_PHASES.some((phase) => input.phaseDone[phase]);
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
    const phase = firstIncompleteMvpPhase(input.phaseDone);
    return {
      status: 'running',
      currentStep: phase ? PHASE_AGENT[phase] : null,
    };
  }

  return { status: input.status, currentStep: null };
}