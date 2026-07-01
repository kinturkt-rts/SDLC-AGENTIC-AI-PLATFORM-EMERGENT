'use client';

import * as React from 'react';
import Link from 'next/link';
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
import { useLogs, useRuns, type LogsFilter } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { AgentName, LogEntry } from '@/src/types';

const LEVELS: (LogEntry['level'] | 'all')[] = ['all', 'info', 'warn', 'error', 'debug'];

const TIME_WINDOWS: { value: string; minutes?: number; label: string }[] = [
  { value: '5', minutes: 5, label: 'Last 5 min' },
  { value: '15', minutes: 15, label: 'Last 15 min' },
  { value: '30', minutes: 30, label: 'Last 30 min' },
  { value: '60', minutes: 60, label: 'Last 1 hour' },
  { value: 'all', label: 'All time' },
];

const MVP_AGENTS: { id: AgentName; label: string }[] = [
  { id: 'orchestrator-agent', label: 'Orchestrator' },
  { id: 'product-agent', label: 'Product' },
  { id: 'architect-agent', label: 'Architect' },
  { id: 'database-agent', label: 'Database' },
  { id: 'developer-agent', label: 'Developer' },
  { id: 'gitlab-agent', label: 'GitLab' },
];

export default function LogsPage() {
  const { data: runs } = useRuns();
  const [level, setLevel] = React.useState<LogEntry['level'] | 'all'>('all');
  const [q, setQ] = React.useState('');
  const [timeWindow, setTimeWindow] = React.useState('30');
  const [runId, setRunId] = React.useState<string>('all');
  const [agent, setAgent] = React.useState<string>('all');

  const minutes = TIME_WINDOWS.find((w) => w.value === timeWindow)?.minutes;
  const filters: LogsFilter = {
    ...(minutes ? { minutes } : {}),
    ...(runId !== 'all' ? { runId } : {}),
    ...(agent !== 'all' ? { agent } : {}),
  };

  const { data: logs, isLoading, isFetching } = useLogs(filters);

  const rows = (logs ?? [])
    .filter((l) => level === 'all' || l.level === level)
    .filter(
      (l) =>
        !q ||
        l.message.toLowerCase().includes(q.toLowerCase()) ||
        l.agent.includes(q.toLowerCase()) ||
        l.runId.toLowerCase().includes(q.toLowerCase()),
    )
    .sort((a, b) => +new Date(b.ts) - +new Date(a.ts));

  const runOptions = [...(runs ?? [])]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, 20);

  return (
    <>
      <PageHeader
        eyebrow="Observe"
        title="Pipeline logs"
        description="Orchestrator output from backend/agents/pipeline/.logs/ — written when you Submit & Run from the dashboard."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Input
              placeholder="Search message, agent, run…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-9 w-[200px] border-white/[0.08] bg-white/[0.02] placeholder:text-muted-foreground/40 focus:border-teal-500/30"
            />
            <Select value={timeWindow} onValueChange={setTimeWindow}>
              <SelectTrigger className="h-9 w-[130px] border-white/[0.08] bg-white/[0.02]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIME_WINDOWS.map((w) => (
                  <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={runId} onValueChange={setRunId}>
              <SelectTrigger className="h-9 w-[160px] border-white/[0.08] bg-white/[0.02]">
                <SelectValue placeholder="All runs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All runs</SelectItem>
                {runOptions.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.projectName} · {r.id.slice(0, 8)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={agent} onValueChange={setAgent}>
              <SelectTrigger className="h-9 w-[140px] border-white/[0.08] bg-white/[0.02]">
                <SelectValue placeholder="All agents" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All agents</SelectItem>
                {MVP_AGENTS.map((a) => (
                  <SelectItem key={a.id} value={a.id}>{a.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={level} onValueChange={(v) => setLevel(v as LogEntry['level'] | 'all')}>
              <SelectTrigger className="h-9 w-[120px] border-white/[0.08] bg-white/[0.02] capitalize">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LEVELS.map((l) => (
                  <SelectItem key={l} value={l} className="capitalize">
                    {l === 'all' ? 'All levels' : l}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />

      {isFetching && !isLoading ? (
        <p className="mb-2 text-xs text-muted-foreground">Refreshing…</p>
      ) : null}

      {isLoading ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No pipeline logs"
          description="Submit a run from the dashboard to generate logs under backend/agents/pipeline/.logs/<runId>.log"
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-card/80 font-mono text-xs">
          {rows.map((l) => (
            <div
              key={l.id}
              className="flex items-start gap-3 border-b border-white/[0.04] px-3 py-2.5 last:border-0 transition-colors hover:bg-white/[0.02]"
            >
              <span className="w-16 shrink-0 text-muted-foreground">{formatRelative(l.ts)}</span>
              <StatusBadge status={l.level} size="sm" className="shrink-0" />
              <span className="w-36 shrink-0 truncate text-teal-400">{l.agent.replace('-agent', '')}</span>
              <Link
                href={`/runs/${l.runId}`}
                className="w-28 shrink-0 truncate text-muted-foreground hover:text-teal-400"
              >
                {l.runId.slice(0, 13)}
              </Link>
              <span className="flex-1 whitespace-pre-wrap break-words text-foreground">{l.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
