import type { LogEntry } from '@/src/types';
import { MVP_LOG_AGENT_SET } from './pipeline-phases';

const NOISE_PATTERNS: RegExp[] = [
  /\bGET \/ping\b/i,
  /^starting server\b/i,
  /^waiting for application startup/i,
  /^application startup complete/i,
  /^started server process\b/i,
  /^finished server process\b/i,
  /^uvicorn running on/i,
  /^info:uvicorn\b/i,
  /^info:botocore\b/i,
  /^debug:botocore\b/i,
];

/** AgentCore health-check and uvicorn startup lines (not pipeline output). */
export function isPipelineLogNoise(message: string): boolean {
  const trimmed = message.trim();
  if (!trimmed) return true;
  return NOISE_PATTERNS.some((re) => re.test(trimmed));
}

export function filterLogRows(
  rows: LogEntry[],
  opts: { q?: string; level?: LogEntry['level'] | 'all'; hideNoise?: boolean },
): LogEntry[] {
  const q = opts.q?.trim().toLowerCase() ?? '';
  return rows.filter((l) => {
    if (opts.hideNoise !== false && isPipelineLogNoise(l.message)) return false;
    if (opts.level && opts.level !== 'all' && l.level !== opts.level) return false;
    if (!q) return true;
    return (
      l.message.toLowerCase().includes(q) ||
      l.agent.toLowerCase().includes(q) ||
      l.runId.toLowerCase().includes(q)
    );
  });
}

/** Strict run scope — only lines tied to this run (by runId or message content). */
export function filterLogsForRun(rows: LogEntry[], runId: string): LogEntry[] {
  const rid = runId.trim();
  if (!rid) return rows;
  return rows.filter(
    (l) => l.runId === rid || l.message.includes(rid),
  );
}

/** When a project is selected, keep logs tied to that project's runs. */
export function filterLogsForProject(
  rows: LogEntry[],
  projectRunIds: Set<string>,
  projectId: string | undefined,
): LogEntry[] {
  if (!projectId || projectRunIds.size === 0) return rows;
  const ids = [...projectRunIds];
  return rows.filter((l) => {
    if (!MVP_LOG_AGENT_SET.has(l.agent)) return false;
    if (l.runId && projectRunIds.has(l.runId)) return true;
    return ids.some((id) => l.message.includes(id));
  });
}

export function filterRunsByQuery<T extends { id: string; projectName: string; pipeline: string }>(
  rows: T[],
  q: string,
): T[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter(
    (r) =>
      r.id.toLowerCase().includes(needle) ||
      r.projectName.toLowerCase().includes(needle) ||
      r.pipeline.toLowerCase().includes(needle),
  );
}
