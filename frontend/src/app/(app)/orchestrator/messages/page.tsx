'use client';

import * as React from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowRight, MessagesSquare } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PageHeader } from '@/src/components/common/PageHeader';
import { MessageTypeBadge } from '@/src/components/common/MessageTypeBadge';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { useAgentMessages, useRuns } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { AgentMessage } from '@/src/types';

export default function MessagesPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-80 w-full rounded-lg" />}>
      <MessagesInner />
    </React.Suspense>
  );
}

function MessagesInner() {
  const searchParams = useSearchParams();
  const initial = searchParams.get('correlationId') ?? 'all';
  const { data: runs } = useRuns();
  const hasLiveRuns = (runs ?? []).some((r) => r.status === 'running' || r.status === 'paused');
  const { data: all, isLoading } = useAgentMessages(undefined, hasLiveRuns);
  const [correlationId, setCorrelationId] = React.useState<string>(initial);

  React.useEffect(() => {
    setCorrelationId(searchParams.get('correlationId') ?? 'all');
  }, [searchParams]);

  const correlationIds = Array.from(new Set((all ?? []).map((m) => m.correlationId)));
  const rows = (all ?? [])
    .filter((m) => correlationId === 'all' || m.correlationId === correlationId)
    .sort((a, b) => +new Date(a.ts) - +new Date(b.ts));

  const columns: Column<AgentMessage>[] = [
    { key: 'ts', header: 'Time', render: (m) => <span className="text-muted-foreground">{formatRelative(m.ts)}</span> },
    { key: 'type', header: 'Type', render: (m) => <MessageTypeBadge type={m.type} /> },
    {
      key: 'route',
      header: 'From → To',
      render: (m) => (
        <span className="flex items-center gap-1 font-mono text-xs">
          <span className="text-foreground">{m.from}</span>
          <ArrowRight className="h-3 w-3 text-muted-foreground" />
          <span className="text-foreground">{m.to}</span>
        </span>
      ),
    },
    { key: 'summary', header: 'Summary', className: 'max-w-md', render: (m) => <span className="line-clamp-2 text-muted-foreground">{m.summary}</span> },
    { key: 'correlationId', header: 'Thread', render: (m) => <button onClick={() => setCorrelationId(m.correlationId)} className="font-mono text-[11px] text-teal-600 hover:underline dark:text-teal-400" title="Click to filter to this thread">{m.correlationId}</button> },
    { key: 'runId', header: 'Run', render: (m) => <Link href={`/runs/${m.runId}`} className="font-mono text-[11px] text-muted-foreground hover:text-teal-600 hover:underline">{m.runId}</Link> },
  ];

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground">
        <Link href="/orchestrator"><ArrowLeft className="h-4 w-4" /> Orchestrator</Link>
      </Button>

      <PageHeader
        eyebrow="Design"
        title="Agent Messages"
        description="Every message the orchestrator and a specialist agent exchange for one phase, generated live as runs progress (assign → in progress → done, or failed). Each row belongs to a thread — one phase within one run — so you can follow a single handoff from start to finish."
        actions={
          <Select value={correlationId} onValueChange={setCorrelationId}>
            <SelectTrigger className="h-9 w-[220px]"><SelectValue placeholder="Filter by thread" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All threads</SelectItem>
              {correlationIds.map((c) => (
                <SelectItem key={c} value={c} className="font-mono text-xs">{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      {correlationId !== 'all' ? (
        <div className="flex items-center gap-2 text-sm">
          <MessagesSquare className="h-4 w-4 text-teal-500" />
          <span className="text-muted-foreground">Showing thread</span>
          <code className="font-mono text-xs text-foreground">{correlationId}</code>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setCorrelationId('all')}>Clear filter</Button>
        </div>
      ) : null}

      {isLoading ? <Skeleton className="h-80 w-full rounded-lg" /> : <DataTable columns={columns} rows={rows} getRowId={(m) => m.id} empty="No messages for this thread." />}
    </>
  );
}
