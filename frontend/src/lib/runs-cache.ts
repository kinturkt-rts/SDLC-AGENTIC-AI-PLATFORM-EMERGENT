import { invalidateCacheKey, invalidateCacheKeys } from './request-cache';

export const LIST_RUNS_CACHE_KEY = 'listRuns';

const RUNS_RELATED_CACHE_KEYS = [
  LIST_RUNS_CACHE_KEY,
  's3RunArtifactIndex',
  'getDashboardSummary',
  'listProjects',
  'listArtifacts',
  'listRecentActivity:12',
] as const;

/** Drop cached run/dashboard reads after a pipeline status change. */
export function invalidateRunsCache(): void {
  invalidateCacheKeys(...RUNS_RELATED_CACHE_KEYS);
}

export function invalidateListRunsCache(): void {
  invalidateCacheKey(LIST_RUNS_CACHE_KEY);
}
