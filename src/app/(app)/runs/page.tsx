'use client';

import * as React from 'react';
import { Workflow } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
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
  const [selected, setSelected] = React.useState<PipelineRun | null>(null);

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
        description="Every SDLC pipeline execution across projects. Click a run to inspect its phase timeline."
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
        <DataTable columns={columns} rows={rows} getRowId={(r) => r.id} onRowClick={(r) => setSelected(r)} empty="No runs match this filter." />
      )}

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full sm:max-w-md">
          {selected ? (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <Workflow className="h-4 w-4 text-teal-500" /> {selected.projectName}
                </SheetTitle>
                <SheetDescription className="font-mono text-xs">{selected.id} · {selected.pipeline}</SheetDescription>
              </SheetHeader>

              <div className="mt-4 flex items-center justify-between rounded-md border border-border p-3">
                <StatusBadge status={selected.status} />
                <span className="text-sm text-muted-foreground">Elapsed {formatDuration(selected.elapsedSec)}</span>
              </div>

              <div className="mt-6">
                <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Phase timeline</p>
                <ol className="relative space-y-4 border-l border-border pl-5">
                  {selected.steps.map((step) => (
                    <li key={step.id} className="relative">
                      <span className="absolute -left-[23px] top-1 h-3 w-3 rounded-full border-2 border-background bg-border" />
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium capitalize text-foreground">{step.phase}</p>
                        <StatusBadge status={step.status} size="sm" />
                      </div>
                      <p className="font-mono text-xs text-muted-foreground">{step.agent}</p>
                      {step.durationSec != null ? <p className="text-xs text-muted-foreground">took {formatDuration(step.durationSec)}</p> : null}
                    </li>
                  ))}
                </ol>
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </>
  );
}
