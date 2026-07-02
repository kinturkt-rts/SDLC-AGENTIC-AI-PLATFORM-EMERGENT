import { MVP_TIMELINE_PHASES, PHASE_AGENT } from './pipeline-phases';
import type { RunStatus, SdlcPhase } from '@/src/types';

/** No log/S3 activity for this long → treat "running" as stalled (orchestrator timeout is up to 30 min). */
export const RUN_LIVE_IDLE_MS = 60 * 60 * 1000;

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

export function parseLogTerminalStatus(
  log: string | null,
): { status: 'completed' | 'failed'; error?: string } | null {
  if (!log?.trim()) return null;
  const lower = log.toLowerCase();

  if (
    lower.includes('sdlc pipeline completed') ||
    /\bstatus:\s*success\b/.test(lower) ||
    /\[apply-rds-local\]\s+ok\b/i.test(log)
  ) {
    return { status: 'completed' };
  }

  const errLine = log
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l.toLowerCase().startsWith('error:'));
  if (errLine) {
    return { status: 'failed', error: errLine.replace(/^error:\s*/i, '') };
  }

  if (lower.includes('sdlc pipeline failed')) {
    return { status: 'failed', error: 'SDLC pipeline failed' };
  }
  if (/\bstatus:\s*(error|failed)\b/i.test(log)) {
    return { status: 'failed', error: 'Orchestrator invoke failed' };
  }
  if (/\bfailed \(exit \d+\)/i.test(log) || lower.includes('traceback (most recent call last)')) {
    return { status: 'failed', error: 'Smoke script failed' };
  }

  return null;
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

/** Derive truthful run status from logs, S3 artifacts, and last activity — not stale run.json alone. */
export function reconcileRunStatus(input: ReconcileRunInput): ReconcileRunResult {
  const terminal = parseLogTerminalStatus(input.logText);
  if (terminal?.status === 'completed') {
    return { status: 'completed', currentStep: null };
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

  if (mvpPipelineComplete(input.phaseDone)) {
    return { status: 'completed', currentStep: null };
  }

  const idleMs = Date.now() - lastRunActivityMs(input);
  const isActiveStatus = input.status === 'running' || input.status === 'queued';

  if (isActiveStatus && idleMs > RUN_LIVE_IDLE_MS) {
    const anyProgress = MVP_TIMELINE_PHASES.some((phase) => input.phaseDone[phase]);
    return {
      status: 'failed',
      currentStep: null,
      error: anyProgress
        ? 'Pipeline stalled (no activity in the last hour)'
        : 'Pipeline abandoned (never progressed)',
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
