import type { LogEntry } from '@/src/types';

export function filterLogRows(
  rows: LogEntry[],
  opts: { q?: string; level?: LogEntry['level'] | 'all' },
): LogEntry[] {
  const q = opts.q?.trim().toLowerCase() ?? '';
  return rows.filter((l) => {
    if (opts.level && opts.level !== 'all' && l.level !== opts.level) return false;
    if (!q) return true;
    return (
      l.message.toLowerCase().includes(q) ||
      l.agent.toLowerCase().includes(q) ||
      l.runId.toLowerCase().includes(q)
    );
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
