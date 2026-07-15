import type { AgentName, PipelineRun, PipelineStep } from '@/src/types';

/** Ops metrics derived from pipeline step history for one agent. */
export interface AgentOpsMetrics {
  /** Completed/failed steps considered (queued/running excluded). */
  sampleSize: number;
  successCount: number;
  failCount: number;
  /** 0–100; null when no finished steps. */
  successRatePct: number | null;
  /** Mean durationSec over steps that recorded duration. */
  avgDurationSec: number | null;
  /** ISO timestamp of most recent step activity for this agent. */
  lastActiveAt: string | null;
}

function stepWhen(step: PipelineStep, run: PipelineRun): string | null {
  return step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt ?? null;
}

/**
 * Aggregate success rate, avg duration, and last-active time per agent
 * from existing pipeline run steps (frontend-only; no backend changes).
 */
export function computeAgentOpsMetrics(
  agentId: string,
  runs: PipelineRun[] | undefined,
): AgentOpsMetrics {
  let successCount = 0;
  let failCount = 0;
  let durationSum = 0;
  let durationN = 0;
  let lastActiveAt: string | null = null;

  for (const run of runs ?? []) {
    for (const step of run.steps) {
      if (step.agent !== (agentId as AgentName)) continue;
      if (
        step.status === 'queued' ||
        step.status === 'running' ||
        step.status === 'skipped' ||
        step.status === 'waiting_for_human'
      ) {
        const when = stepWhen(step, run);
        if (when && (!lastActiveAt || when > lastActiveAt)) lastActiveAt = when;
        continue;
      }

      if (step.status === 'completed') successCount += 1;
      else if (step.status === 'failed') failCount += 1;
      else continue;

      if (typeof step.durationSec === 'number' && Number.isFinite(step.durationSec)) {
        durationSum += step.durationSec;
        durationN += 1;
      }

      const when = stepWhen(step, run);
      if (when && (!lastActiveAt || when > lastActiveAt)) lastActiveAt = when;
    }
  }

  const sampleSize = successCount + failCount;
  return {
    sampleSize,
    successCount,
    failCount,
    successRatePct: sampleSize > 0 ? Math.round((successCount / sampleSize) * 100) : null,
    avgDurationSec: durationN > 0 ? durationSum / durationN : null,
    lastActiveAt,
  };
}

export function computeAllAgentOpsMetrics(
  agentIds: string[],
  runs: PipelineRun[] | undefined,
): Record<string, AgentOpsMetrics> {
  const out: Record<string, AgentOpsMetrics> = {};
  for (const id of agentIds) {
    out[id] = computeAgentOpsMetrics(id, runs);
  }
  return out;
}
