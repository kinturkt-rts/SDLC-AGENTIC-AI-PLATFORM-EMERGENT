'use client';

import * as React from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
import { EmptyState } from '@/src/components/common/EmptyState';
import { LogTable } from '@/src/components/logs/LogTable';
import { useLogs, useProjects, useRun, useRuns, type LogsFilter } from '@/src/lib/queries';
import { filterLogRows, filterLogsForProject } from '@/src/lib/log-filters';
import { useUiStore } from '@/src/store/ui-store';
import type { AgentName, LogEntry } from '@/src/types';

const LEVELS: (LogEntry['level'] | 'all')[] = ['all', 'info', 'warn', 'error', 'debug'];

const TIME_WINDOWS: { value: string; minutes?: number; label: string }[] = [
  { value: '15', minutes: 15, label: 'Last 15 min' },
  { value: '30', minutes: 30, label: 'Last 30 min' },
  { value: '60', minutes: 60, label: 'Last 1 hour' },
  { value: '240', minutes: 240, label: 'Last 4 hours' },
  { value: '1440', minutes: 1440, label: 'Last 24 hours' },
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
  return (
    <React.Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
      <LogsInner />
    </React.Suspense>
  );
}

function LogsInner() {
  const searchParams = useSearchParams();
  const paramRunId = searchParams.get('runId')?.trim() ?? '';

  const { data: runs } = useRuns();
  const { data: projects } = useProjects();
  const logsProjectId = useUiStore((s) => s.logsProjectId);

  const [level, setLevel] = React.useState<LogEntry['level'] | 'all'>('all');
  const [q, setQ] = React.useState('');
  const [timeWindow, setTimeWindow] = React.useState('240');
  const [selectedRunId, setSelectedRunId] = React.useState(paramRunId || 'all');
  const [agent, setAgent] = React.useState<string>('all');

  const scopedRuns = logsProjectId
    ? (runs ?? []).filter((r) => r.projectId === logsProjectId)
    : (runs ?? []);
  const projectRunIds = new Set(scopedRuns.map((r) => r.id));
  const projectName = logsProjectId
    ? (projects?.find((p) => p.id === logsProjectId)?.name ?? logsProjectId)
    : null;

  const runOptions = [...scopedRuns]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, 40);

  React.useEffect(() => {
    if (paramRunId) setSelectedRunId(paramRunId);
  }, [paramRunId]);

  React.useEffect(() => {
    if (selectedRunId === 'all') return;
    const belongs = scopedRuns.some((r) => r.id === selectedRunId);
    if (!belongs && runOptions.length > 0) setSelectedRunId(runOptions[0]?.id ?? 'all');
  }, [logsProjectId, selectedRunId, scopedRuns, runOptions]);

  const activeRunId = selectedRunId !== 'all' ? selectedRunId : undefined;
  const { data: activeRun } = useRun(activeRunId ?? '');
  const isLiveRun = activeRun?.status === 'running' || activeRun?.status === 'paused';

  const minutes = TIME_WINDOWS.find((w) => w.value === timeWindow)?.minutes;
  const logFilters: LogsFilter = {
    ...(activeRunId ? { runId: activeRunId } : minutes ? { minutes } : {}),
    ...(agent !== 'all' ? { agent } : {}),
    limit: 2000,
  };

  const { data: logs, isLoading, isFetching } = useLogs(logFilters, isLiveRun || !activeRunId);

  let rows = filterLogRows(logs ?? [], { q, level });
  if (!activeRunId && logsProjectId) {
    rows = filterLogsForProject(rows, projectRunIds, logsProjectId);
  }
  rows = rows.sort((a, b) => +new Date(b.ts) - +new Date(a.ts));

  const description = activeRun
    ? `Live CloudWatch for ${activeRun.projectName} · run ${activeRun.id.slice(0, 8)}…`
    : projectName
      ? `Live CloudWatch for ${projectName} - pick a run or browse recent activity.`
      : 'Live CloudWatch from AgentCore pipeline agents.';

  return (
    <>
      <PageHeader
        eyebrow="Observe"
        title="Pipeline logs"
        description={description}
        toolbar={
          <>
            <Input
              placeholder="Search message or agent…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-9 w-full min-w-[200px] flex-1 border-white/[0.08] bg-white/[0.02] placeholder:text-muted-foreground/40 focus:border-teal-500/30 sm:max-w-xs"
            />
            <Select value={selectedRunId} onValueChange={setSelectedRunId}>
              <SelectTrigger className="h-9 w-[200px] border-white/[0.08] bg-white/[0.02]">
                <SelectValue placeholder="All runs" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All runs</SelectItem>
                {runOptions.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.projectName} · {r.id.slice(0, 8)} · {r.status}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!activeRunId ? (
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
            ) : null}
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
        Live AgentCore stdout from CloudWatch.
        {activeRunId ? (
          <>
            {' '}
            Showing the full run window (all agents).
            <Link href={`/runs/${activeRunId}`} className="ml-1 text-teal-400 hover:underline">
              Run detail
            </Link>
          </>
        ) : (
          <> Select a run for full per-run output, or use All runs with a time window.</>
        )}
      </p>

      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="text-teal-400">CloudWatch</span>
        <span>·</span>
        <span>{rows.length} entries</span>
        {isFetching && !isLoading ? <span>· live</span> : null}
      </div>

      {isLoading ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ScrollText}
          title="No log events"
          description={
            activeRunId
              ? 'No CloudWatch output in this run window yet. Live runs refresh every few seconds.'
              : 'Widen the time window or pick a specific run from the dropdown.'
          }
        />
      ) : (
        <LogTable rows={rows} showRunColumn={!activeRunId} />
      )}
    </>
  );
}
