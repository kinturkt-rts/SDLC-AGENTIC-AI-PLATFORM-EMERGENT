import type { PipelineRun } from '@/src/types';
import type { ActivityFeedItem } from './run-events';

/** Only surface events from the last 30 minutes or since the run started. */
export const LIVE_ACTIVITY_MAX_AGE_MS = 30 * 60 * 1000;

export function filterLiveRuns(runs: PipelineRun[]): PipelineRun[] {
  return runs.filter((r) => r.status === 'running' || r.status === 'paused');
}

/** Earliest timestamp that still counts as live for a given run. */
export function liveActivityCutoffMs(run: PipelineRun, nowMs = Date.now()): number {
  const started = Date.parse(run.startedAt);
  const startedMs = Number.isFinite(started) ? started - 60_000 : nowMs;
  return Math.max(nowMs - LIVE_ACTIVITY_MAX_AGE_MS, startedMs);
}

export function isRecentLiveTs(ts: string, run: PipelineRun, nowMs = Date.now()): boolean {
  const t = Date.parse(ts);
  if (!Number.isFinite(t)) return false;
  return t >= liveActivityCutoffMs(run, nowMs);
}

export function isLiveActivityStream(stream?: ActivityFeedItem['stream']): boolean {
  return stream === 'cloudwatch' || stream === 'artifact' || stream === 'pipeline-log';
}
