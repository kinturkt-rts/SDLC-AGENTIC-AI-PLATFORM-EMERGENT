'use client';

import * as React from 'react';
import { Database, FileJson, ChevronDown } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useContextItems, usePipelineContext } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { ContextItem, PipelineContext } from '@/src/types';

function PipelineContextCard({ ctx }: { ctx: PipelineContext }) {
  const [open, setOpen] = React.useState(false);
  const rows: [string, React.ReactNode][] = [
    ['targetApp', ctx.targetApp],
    ['prdPath', ctx.prdPath],
    ['designDocPath', ctx.designDocPath],
    ['diagramPaths', ctx.diagramPaths.join(', ')],
    ['productAgentOutput', ctx.productAgentOutput],
    ['architectSummary', ctx.architectSummary],
    ['dbOutputDir', ctx.dbOutputDir],
    ['preferredSqlPath', ctx.preferredSqlPath],
  ];
  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <FileJson className="h-4 w-4 text-teal-500" />
        <h3 className="text-sm font-semibold text-foreground">Pipeline context</h3>
        <span className="text-xs text-muted-foreground">handoff JSON written by agents</span>
      </div>
      <dl className="divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-col gap-0.5 px-4 py-2 sm:flex-row sm:items-center sm:gap-4">
            <dt className="w-48 shrink-0 font-mono text-xs text-muted-foreground">{k}</dt>
            <dd className="break-all font-mono text-xs text-foreground">{v}</dd>
          </div>
        ))}
      </dl>
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger className="flex w-full items-center gap-1.5 border-t border-border px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground">
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} /> View raw JSON
        </CollapsibleTrigger>
        <CollapsibleContent>
          <pre className="max-h-72 overflow-auto border-t border-border bg-muted/40 p-3 text-[11px] leading-relaxed text-foreground">
            {JSON.stringify(ctx, null, 2)}
          </pre>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

export function ContextView({ projectSlug }: { projectSlug: string }) {
  const all = projectSlug === 'all';
  const { data: items, isLoading } = useContextItems(all ? undefined : projectSlug);
  const { data: pipeline } = usePipelineContext(all ? '' : projectSlug);

  const columns: Column<ContextItem>[] = [
    { key: 'key', header: 'Key', render: (c) => <span className="font-mono text-foreground">{c.key}</span> },
    ...(all
      ? [{ key: 'projectName', header: 'Project', render: (c: ContextItem) => <span className="text-foreground">{c.projectName}</span> }]
      : []),
    { key: 'scope', header: 'Scope', render: (c) => <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] capitalize text-muted-foreground">{c.scope}</span> },
    { key: 'type', header: 'Type', render: (c) => <span className="capitalize text-muted-foreground">{c.type}</span> },
    { key: 'summary', header: 'Summary', className: 'max-w-md', render: (c) => <span className="line-clamp-2 text-muted-foreground">{c.summary}</span> },
    { key: 'tokens', header: 'Tokens', align: 'right', render: (c) => <span className="font-mono text-muted-foreground">{c.tokens.toLocaleString()}</span> },
    { key: 'updated', header: 'Updated', render: (c) => <span className="text-muted-foreground">{formatRelative(c.updatedAt)}</span> },
  ];

  if (isLoading) return <Skeleton className="h-72 w-full rounded-lg" />;

  return (
    <div className="space-y-4">
      {!all && pipeline ? <PipelineContextCard ctx={pipeline} /> : null}
      {(items ?? []).length === 0 ? (
        <EmptyState
          icon={Database}
          title="No context yet"
          description={all ? 'No context entries.' : 'This project has no context. It is created when a pipeline run produces agent handoff.'}
        />
      ) : (
        <DataTable columns={columns} rows={items ?? []} getRowId={(c) => c.id} />
      )}
    </div>
  );
}
