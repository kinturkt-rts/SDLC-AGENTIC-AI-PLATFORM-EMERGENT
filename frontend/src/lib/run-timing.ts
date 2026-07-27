import { promises as fs } from 'fs';
import path from 'path';
import { getRunArtifactJson, isS3Store } from './artifact-store';
import { getBackendRoot } from './repo-root';
import { AGENT_IDS } from './token-display';
import type { RunStatus } from '@/src/types';

export interface RunTimingInput {
  startedAt: string;
  status: RunStatus;
  liveStartedAt?: string | null;
  liveFinishedAt?: string | null;
  logMtimeMs: number;
  s3LatestMs: number;
  s3EarliestMs: number;
  telemetryElapsedSec?: number | null;
  stepsDurationSec?: number | null;
}

export function resolveRunTimings(input: RunTimingInput): {
  startedAt: string;
  finishedAt: string | null;
  elapsedSec: number;
} {
  let startedMs = Date.parse(input.liveStartedAt ?? input.startedAt);
  if (!Number.isFinite(startedMs)) startedMs = Date.now();

  const isTerminal =
    input.status === 'completed' ||
    input.status === 'awaiting_deploy' ||
    input.status === 'failed' ||
    input.status === 'cancelled';

  if (
    input.s3EarliestMs > 0 &&
    input.s3LatestMs > input.s3EarliestMs + 60_000 &&
    input.liveStartedAt == null &&
    Math.abs(startedMs - input.s3LatestMs) < 5000
  ) {
    startedMs = input.s3EarliestMs;
  }

  if (input.liveFinishedAt) {
    const finishedMs = Date.parse(input.liveFinishedAt);
    const elapsedSec = Number.isFinite(finishedMs)
      ? Math.max(1, Math.floor((finishedMs - startedMs) / 1000))
      : 1;
    return {
      startedAt: new Date(startedMs).toISOString(),
      finishedAt: input.liveFinishedAt,
      elapsedSec,
    };
  }

  if (!isTerminal) {
    return {
      startedAt: new Date(startedMs).toISOString(),
      finishedAt: null,
      elapsedSec: Math.max(1, Math.floor((Date.now() - startedMs) / 1000)),
    };
  }

  let endMs = Math.max(startedMs, input.logMtimeMs || 0, input.s3LatestMs || 0);
  let elapsedSec = Math.floor((endMs - startedMs) / 1000);

  if (elapsedSec < 2 && input.telemetryElapsedSec && input.telemetryElapsedSec > 0) {
    elapsedSec = Math.round(input.telemetryElapsedSec);
    endMs = startedMs + elapsedSec * 1000;
  } else if (elapsedSec < 2 && input.stepsDurationSec && input.stepsDurationSec > 0) {
    elapsedSec = Math.round(input.stepsDurationSec);
    endMs = startedMs + elapsedSec * 1000;
  } else if (
    elapsedSec < 2 &&
    input.s3EarliestMs > 0 &&
    input.s3LatestMs > input.s3EarliestMs
  ) {
    startedMs = input.s3EarliestMs;
    endMs = input.s3LatestMs;
    elapsedSec = Math.floor((endMs - startedMs) / 1000);
  }

  elapsedSec = Math.max(1, elapsedSec);

  return {
    startedAt: new Date(startedMs).toISOString(),
    finishedAt: new Date(endMs).toISOString(),
    elapsedSec,
  };
}

function telemetryMatchesRun(
  doc: Record<string, unknown>,
  runId: string,
): boolean {
  const snapRunId = typeof doc.runId === 'string' ? doc.runId.trim() : '';
  if (!snapRunId) return true;
  return snapRunId === runId;
}

/** Sum MVP agent elapsed seconds for a run (S3 run folder or local pipeline dir). */
export async function loadRunTelemetryElapsedSec(
  slug: string,
  runId: string,
): Promise<number | null> {
  let total = 0;
  let found = false;

  if (isS3Store()) {
    for (const agentId of AGENT_IDS) {
      for (const rel of [
        `${slug}/telemetry/${agentId}-telemetry.json`,
        `${slug}/handoffs/${agentId}-telemetry.json`,
      ]) {
        const doc = await getRunArtifactJson(runId, rel);
        if (!doc || !telemetryMatchesRun(doc, runId)) continue;
        const elapsed = typeof doc.elapsedSec === 'number' ? doc.elapsedSec : 0;
        if (elapsed > 0) {
          total += elapsed;
          found = true;
        }
        break;
      }
    }
  }

  const pipelineDir = path.join(getBackendRoot(), 'agents', 'pipeline');
  for (const agentId of AGENT_IDS) {
    const filePath = path.join(pipelineDir, `${slug}.${agentId}-telemetry.json`);
    try {
      let raw = await fs.readFile(filePath, 'utf-8');
      if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
      const doc = JSON.parse(raw) as Record<string, unknown>;
      if (!telemetryMatchesRun(doc, runId)) continue;
      const elapsed = typeof doc.elapsedSec === 'number' ? doc.elapsedSec : 0;
      if (elapsed > 0) {
        if (!found || !isS3Store()) {
          total += elapsed;
          found = true;
        }
      }
    } catch {
      // skip missing local telemetry
    }
  }

  return found && total > 0 ? Math.round(total * 100) / 100 : null;
}
