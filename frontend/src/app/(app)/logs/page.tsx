'use client';

import * as React from 'react';
import Link from 'next/link';
import { ScrollText, Cloud, HardDrive } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useLogs, useProjects, useRuns, type LogsFilter } from '@/src/lib/queries';
import { filterLogRows } from '@/src/lib/log-filters';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative } from '@/src/lib/format';
import type { AgentName, LogEntry } from '@/src/types';

type LogSource = 'cloudwatch' | 'local';

const LEVELS: (LogEntry['level'] | 'all')[] = ['all', 'info', 'warn', 'error', 'debug'];

const TIME_WINDOWS: { value: string; minutes?: number; label: string }[] = [
  { value: '5', minutes: 5, label: 'Last 5 min' },
  { value: '15', minutes: 15, label: 'Last 15 min' },
  { value: '30', minutes: 30, label: 'Last 30 min' },
  { value: '60', minutes: 60, label: 'Last 1 hour' },
  { value: '240', minutes: 240, label: 'Last 4 hours' },
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
  const { data: projects } = useProjects();
  const logsProjectId = useUiStore((s) => s.logsProjectId);
  const [source, setSource] = React.useState<LogSource>('cloudwatch');
  const [level, setLevel] = React.useState<LogEntry['level'] | 'all'>('all');
  const [q, setQ] = React.useState('');
  const [timeWindow, setTimeWindow] = React.useState('60');
  const [runId, setRunId] = React.useState<string>('all');
  const [agent, setAgent] = React.useState<string>('all');

  const minutes = TIME_WINDOWS.find((w) => w.value === timeWindow)?.minutes;
  const filters: LogsFilter = {
    source,
    ...(minutes ? { minutes } : {}),
    ...(runId !== 'all' ? { runId } : {}),
    ...(agent !== 'all' ? { agent } : {}),
    limit: 500,
  };

  const { data: logs, isLoading, isFetching } = useLogs(filters);

  const scopedRuns = logsProjectId
    ? (runs ?? []).filter((r) => r.projectId === logsProjectId)
    : (runs ?? []);
  const projectRunIds = new Set(scopedRuns.map((r) => r.id));
  const projectName = logsProjectId
    ? (projects?.find((p) => p.id === logsProjectId)?.name ?? logsProjectId)
    : 'all projects';

  React.useEffect(() => {
    if (runId === 'all') return;
    const belongs = scopedRuns.some((r) => r.id === runId);
    if (!belongs) setRunId('all');
  }, [logsProjectId, runId, scopedRuns]);

  const rows = filterLogRows(logs ?? [], { q, level })
    .filter((l) => !logsProjectId || !l.runId || projectRunIds.has(l.runId))
    .sort((a, b) => +new Date(b.ts) - +new Date(a.ts));

  const runOptions = [...scopedRuns]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, 20);

  const isCloudWatch = source === 'cloudwatch';

  return (
    <>
      <PageHeader
        eyebrow="Observe"
        title="Pipeline logs"
        description={
          logsProjectId
            ? `Agent and orchestrator output for ${projectName}.`
            : 'Agent and orchestrator output across all projects.'
        }
        actions={
          <Tabs value={source} onValueChange={(v) => setSource(v as LogSource)}>
            <TabsList className="h-9">
              <TabsTrigger value="cloudwatch" className="gap-1.5 text-xs">
                <Cloud className="h-3.5 w-3.5" /> CloudWatch
              </TabsTrigger>
              <TabsTrigger value="local" className="gap-1.5 text-xs">
                <HardDrive className="h-3.5 w-3.5" /> Local
              </TabsTrigger>
            </TabsList>
          </Tabs>
        }
        toolbar={
          <>
            <Input
              placeholder="Search message, agent, run…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-9 w-full min-w-[200px] flex-1 border-white/[0.08] bg-white/[0.02] placeholder:text-muted-foreground/40 focus:border-teal-500/30 sm:max-w-xs"
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
          </>
        }
      />

      <p className="mb-3 text-sm text-muted-foreground">
        {isCloudWatch ? (
          <>CloudWatch logs of agents - live stdout from deployed Bedrock AgentCore runtimes.</>
        ) : (
          <>Local pipeline logs - orchestrator output captured on this machine.</>
        )}
      </p>

      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        <span className={isCloudWatch ? 'text-teal-400' : ''}>
          {isCloudWatch ? 'CloudWatch' : 'Local'}
        </span>
        <span>·</span>
        <span>{rows.length} entries</span>
        {isFetching && !isLoading ? <span>· refreshing…</span> : null}
      </div>

      {isLoading ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title={isCloudWatch ? 'No CloudWatch log events' : 'No pipeline logs'}
          description={
            isCloudWatch
              ? 'No events in this window for the selected agent(s). Try widening the time window, or switch to Local to view smoke-script captures.'
              : 'Start a pipeline run from the dashboard to capture orchestrator output locally.'
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-white/[0.06] bg-card/80 font-mono text-xs">
          {rows.map((l) => (
            <div
              key={l.id}
              className="flex items-start gap-3 border-b border-white/[0.04] px-3 py-2.5 last:border-0 transition-colors hover:bg-white/[0.02]"
            >
              <span className="w-32 shrink-0 text-muted-foreground">{formatRelative(l.ts)}</span>
              <StatusBadge status={l.level} size="sm" className="shrink-0" />
              <span className="w-32 shrink-0 truncate text-teal-400">{l.agent.replace('-agent', '')}</span>
              {l.runId ? (
                <Link
                  href={`/runs/${l.runId}`}
                  className="w-28 shrink-0 truncate text-muted-foreground hover:text-teal-400"
                >
                  {l.runId.slice(0, 13)}
                </Link>
              ) : (
                <span className="w-28 shrink-0 truncate text-muted-foreground/40">-</span>
              )}
              <span className="flex-1 whitespace-pre-wrap break-words text-foreground">{l.message}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
