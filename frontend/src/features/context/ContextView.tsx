'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
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
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { useContextItems, usePipelineContext } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import { useUiStore } from '@/src/store/ui-store';
import type { ContextItem, PipelineContext } from '@/src/types';

function PipelineContextCard({ ctx, projectSlug }: { ctx: PipelineContext; projectSlug: string }) {
  const [rawOpen, setRawOpen] = React.useState(false);
  const router = useRouter();
  const setArtifactsProjectId = useUiStore((s) => s.setArtifactsProjectId);

  const gitlabUrl = ctx.gitlabMergeRequestUrl ?? ctx.gitlabBranchUrl ?? null;
  const rawRows: [string, React.ReactNode][] = [
    ['Application', ctx.targetApp],
    ['Run ID', ctx.runId],
    [
      'Pipeline state',
      ctx.runStatus ? <StatusBadge status={ctx.runStatus} size="sm" /> : null,
    ],
    ['Active agent', ctx.activeAgent],
    [
      'Completed agents',
      ctx.completedAgents && ctx.completedAgents.length > 0 ? ctx.completedAgents.join(', ') : null,
    ],
    [
      'GitLab reference',
      gitlabUrl ? (
        <a href={gitlabUrl} target="_blank" rel="noreferrer" className="text-teal-600 hover:underline dark:text-teal-400">
          {ctx.gitlabMergeRequestUrl ? 'Merge request' : 'Branch'}
        </a>
      ) : null,
    ],
    [
      'Live URL',
      ctx.liveUrl ? (
        <a href={ctx.liveUrl} target="_blank" rel="noreferrer" className="break-all text-teal-600 hover:underline dark:text-teal-400">
          {ctx.liveUrl}
        </a>
      ) : null,
    ],
    [
      'Generated artifacts',
      <button
        key="artifacts-link"
        type="button"
        onClick={() => {
          setArtifactsProjectId(projectSlug);
          router.push('/artifacts');
        }}
        className="text-teal-600 hover:underline dark:text-teal-400"
      >
        View artifacts for this app →
      </button>,
    ],
    ['Input brief', ctx.inputPath],
    ['PRD path', ctx.prdPath],
    ['Design doc path', ctx.designDocPath],
    ['Diagram paths', ctx.diagramPaths.join(', ')],
    ['Product summary', ctx.productAgentOutput],
    ['Architecture summary', ctx.architectSummary],
    ['DB output directory', ctx.dbOutputDir],
    ['Preferred SQL path', ctx.preferredSqlPath],
    ['Last updated', ctx.lastUpdatedAt ? formatRelative(ctx.lastUpdatedAt) : null],
  ];
  const rows = rawRows.filter(([, value]) => value != null && (typeof value !== 'string' || value.trim().length > 0));
  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <FileJson className="h-4 w-4 text-teal-500" />
        <h3 className="text-sm font-semibold text-foreground">Pipeline context</h3>
        <span className="text-xs text-muted-foreground">readable summary of the agent handoff for this app</span>
      </div>
      <dl className="divide-y divide-border">
        {rows.map(([k, v]) => (
          <div key={k} className="flex flex-col gap-0.5 px-4 py-2 sm:flex-row sm:items-center sm:gap-4">
            <dt className="w-48 shrink-0 text-xs font-medium text-muted-foreground">{k}</dt>
            <dd className="break-words text-xs text-foreground">{v}</dd>
          </div>
        ))}
      </dl>
      <Collapsible open={rawOpen} onOpenChange={setRawOpen}>
        <CollapsibleTrigger className="flex w-full items-center gap-1.5 border-t border-border px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground">
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${rawOpen ? 'rotate-180' : ''}`} />
          Advanced: raw context JSON
        </CollapsibleTrigger>
        <CollapsibleContent>
          <p className="border-t border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground">
            For debugging only. Secret-shaped fields (tokens, passwords, credentials) are redacted.
          </p>
          <pre className="max-h-72 overflow-auto border-t border-border bg-muted/40 p-3 text-[11px] leading-relaxed text-foreground">
            {JSON.stringify(ctx.raw ?? ctx, null, 2)}
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
      {!all && pipeline ? <PipelineContextCard ctx={pipeline} projectSlug={projectSlug} /> : null}
      {!all && !pipeline ? (
        <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
          Structured pipeline context isn&apos;t available for this app yet - it&apos;s created once a pipeline run
          produces agent handoff. Individual context entries below (if any) still work as raw memory/document
          references.
        </div>
      ) : null}
      {all ? (
        <p className="text-xs text-muted-foreground">
          Summaries of context entries across every project. Select a project to see its full readable pipeline
          context, including run state and artifact/GitLab references.
        </p>
      ) : null}
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
