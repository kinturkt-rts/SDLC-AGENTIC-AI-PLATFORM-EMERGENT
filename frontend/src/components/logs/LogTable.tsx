import Link from 'next/link';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { formatRelative } from '@/src/lib/format';
import type { LogEntry } from '@/src/types';

export function LogTable({ rows, showRunColumn = true }: { rows: LogEntry[]; showRunColumn?: boolean }) {
  if (rows.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-card/80 font-mono text-xs">
      {rows.map((l) => (
        <div
          key={l.id}
          className="flex items-start gap-3 border-b border-white/[0.04] px-3 py-2.5 last:border-0 transition-colors hover:bg-white/[0.02]"
        >
          <span className="w-32 shrink-0 text-muted-foreground">{formatRelative(l.ts)}</span>
          <StatusBadge status={l.level} size="sm" className="shrink-0" />
          <span className="w-32 shrink-0 truncate text-teal-400">{l.agent.replace('-agent', '')}</span>
          {showRunColumn ? (
            l.runId ? (
              <Link
                href={`/runs/${l.runId}`}
                className="w-28 shrink-0 truncate text-muted-foreground hover:text-teal-400"
              >
                {l.runId.slice(0, 13)}
              </Link>
            ) : (
              <span className="w-28 shrink-0 truncate text-muted-foreground/40">—</span>
            )
          ) : null}
          <span className="flex-1 whitespace-pre-wrap break-words text-foreground">{l.message}</span>
        </div>
      ))}
    </div>
  );
}
