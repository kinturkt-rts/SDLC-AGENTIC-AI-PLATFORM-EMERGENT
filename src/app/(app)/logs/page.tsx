'use client';

import * as React from 'react';
import { ScrollText } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useLogs } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { LogEntry } from '@/src/types';

const LEVELS: (LogEntry['level'] | 'all')[] = ['all', 'info', 'warn', 'error', 'debug'];

export default function LogsPage() {
  const { data: logs, isLoading } = useLogs();
  const [level, setLevel] = React.useState<LogEntry['level'] | 'all'>('all');
  const [q, setQ] = React.useState('');

  const rows = (logs ?? [])
    .filter((l) => level === 'all' || l.level === level)
    .filter((l) => !q || l.message.toLowerCase().includes(q.toLowerCase()) || l.agent.includes(q.toLowerCase()))
    .sort((a, b) => +new Date(b.ts) - +new Date(a.ts));

  return (
    <>
      <PageHeader
        eyebrow="Observe"
        title="Logs"
        description="Streamed events emitted by agents during pipeline runs."
        actions={
          <div className="flex items-center gap-2">
            <Input placeholder="Filter messages..." value={q} onChange={(e) => setQ(e.target.value)} className="h-9 w-[200px]" />
            <Select value={level} onValueChange={(v) => setLevel(v as LogEntry['level'] | 'all')}>
              <SelectTrigger className="h-9 w-[120px] capitalize"><SelectValue /></SelectTrigger>
              <SelectContent>
                {LEVELS.map((l) => <SelectItem key={l} value={l} className="capitalize">{l === 'all' ? 'All levels' : l}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        }
      />

      {isLoading ? (
        <Skeleton className="h-96 w-full rounded-lg" />
      ) : rows.length === 0 ? (
        <EmptyState icon={ScrollText} title="No logs" description="No log entries match your filters." />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card font-mono text-xs">
          {rows.map((l) => (
            <div key={l.id} className="flex items-start gap-3 border-b border-border px-3 py-2 last:border-0 hover:bg-accent/40">
              <span className="w-16 shrink-0 text-muted-foreground">{formatRelative(l.ts)}</span>
              <StatusBadge status={l.level} size="sm" className="shrink-0" />
              <span className="w-40 shrink-0 truncate text-teal-600 dark:text-teal-400">{l.agent}</span>
              <span className="shrink-0 text-muted-foreground">{l.runId}</span>
              <span className="flex-1 text-foreground">{l.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
