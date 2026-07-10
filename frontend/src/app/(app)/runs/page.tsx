'use client';

import { useRouter } from 'next/navigation';
import * as React from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { useProjects, useRuns } from '@/src/lib/queries';
import { filterRunsByQuery } from '@/src/lib/log-filters';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { PipelineRun, RunStatus } from '@/src/types';

const STATUS_OPTIONS: (RunStatus | 'all')[] = ['all', 'running', 'paused', 'queued', 'completed', 'failed', 'cancelled'];

function runActivityMs(run: PipelineRun): number {
  const finished = run.finishedAt ? Date.parse(run.finishedAt) : 0;
  const started = Date.parse(run.startedAt);
  return Math.max(
    Number.isFinite(finished) ? finished : 0,
    Number.isFinite(started) ? started : 0,
  );
}

export default function RunsPage() {
  const { data: runs, isLoading } = useRuns();
  const { data: projects } = useProjects();
  const runsProjectId = useUiStore((s) => s.runsProjectId);
  const filter = useUiStore((s) => s.runStatusFilter);
  const setFilter = useUiStore((s) => s.setRunStatusFilter);
  const router = useRouter();
  const [q, setQ] = React.useState('');

  const projectName = runsProjectId
    ? projects?.find((p) => p.id === runsProjectId)?.name ?? runsProjectId
    : 'all projects';

  const rows = filterRunsByQuery(
    (runs ?? [])
      .filter((r) => !runsProjectId || r.projectId === runsProjectId)
      .filter((r) => filter === 'all' || r.status === filter),
    q,
  ).sort((a, b) => runActivityMs(b) - runActivityMs(a));

  const columns: Column<PipelineRun>[] = [
    { key: 'id', header: 'Run', render: (r) => <span className="font-mono text-xs text-foreground" title={r.id}>{r.id.slice(0, 8)}…</span> },
    { key: 'projectName', header: 'Project', render: (r) => <span className="font-medium text-foreground">{r.projectName}</span> },
    { key: 'pipeline', header: 'Pipeline', render: (r) => <span className="text-muted-foreground">{r.pipeline}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} size="sm" /> },
    { key: 'currentAgent', header: 'Current agent', render: (r) => <span className="text-muted-foreground">{r.currentAgent ?? '\u2014'}</span> },
    { key: 'elapsed', header: 'Elapsed', render: (r) => <span className="text-muted-foreground">{formatDuration(r.elapsedSec)}</span> },
    { key: 'updated', header: 'Updated', render: (r) => <span className="text-muted-foreground">{formatRelative(r.finishedAt ?? r.startedAt)}</span> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="Pipeline Runs"
        description={`Pipeline executions for ${projectName}. Use the Project filter to focus on one app, then open a run for live progress.`}
        toolbar={
          <>
            <Input
              placeholder="Search run id or project…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-9 w-full min-w-[200px] flex-1 border-white/[0.08] bg-white/[0.02] placeholder:text-muted-foreground/40 focus:border-teal-500/30 sm:max-w-xs"
            />
            <Select value={filter} onValueChange={(v) => setFilter(v as RunStatus | 'all')}>
              <SelectTrigger className="h-9 w-[160px] border-white/[0.08] bg-white/[0.02]"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">{s === 'all' ? 'All statuses' : s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />

      {isLoading ? (
        <Skeleton className="h-80 w-full rounded-xl" />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          getRowId={(r) => r.id}
          onRowClick={(r) => router.push(`/runs/${r.id}`)}
          empty="No runs match this filter."
        />
      )}
    </>
  );
}
