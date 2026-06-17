'use client';

import { useRouter } from 'next/navigation';
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
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { useRuns } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { PipelineRun, RunStatus } from '@/src/types';

const STATUS_OPTIONS: (RunStatus | 'all')[] = ['all', 'running', 'paused', 'queued', 'completed', 'failed', 'cancelled'];

export default function RunsPage() {
  const { data: runs, isLoading } = useRuns();
  const filter = useUiStore((s) => s.runStatusFilter);
  const setFilter = useUiStore((s) => s.setRunStatusFilter);
  const router = useRouter();

  const rows = (runs ?? []).filter((r) => filter === 'all' || r.status === filter);

  const columns: Column<PipelineRun>[] = [
    { key: 'id', header: 'Run', render: (r) => <span className="font-mono text-xs text-foreground">{r.id}</span> },
    { key: 'projectName', header: 'Project', render: (r) => <span className="font-medium text-foreground">{r.projectName}</span> },
    { key: 'pipeline', header: 'Pipeline', render: (r) => <span className="text-muted-foreground">{r.pipeline}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} size="sm" /> },
    { key: 'currentAgent', header: 'Current agent', render: (r) => <span className="text-muted-foreground">{r.currentAgent ?? '—'}</span> },
    { key: 'elapsed', header: 'Elapsed', render: (r) => <span className="text-muted-foreground">{formatDuration(r.elapsedSec)}</span> },
    { key: 'triggeredBy', header: 'Triggered by', render: (r) => <span className="font-mono text-xs text-muted-foreground">{r.triggeredBy}</span> },
    { key: 'started', header: 'Started', render: (r) => <span className="text-muted-foreground">{formatRelative(r.startedAt)}</span> },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="Pipeline Runs"
        description="Every SDLC pipeline execution across projects. Click a run to open its detail view."
        actions={
          <Select value={filter} onValueChange={(v) => setFilter(v as RunStatus | 'all')}>
            <SelectTrigger className="h-9 w-[160px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s} className="capitalize">{s === 'all' ? 'All statuses' : s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      {isLoading ? (
        <Skeleton className="h-80 w-full rounded-lg" />
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
