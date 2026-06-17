'use client';

import Link from 'next/link';
import { ArrowLeft, GitBranch, FileBox, Clock, ExternalLink } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { EmptyState } from '@/src/components/common/EmptyState';
import {
  useProject,
  useRuns,
  useArtifacts,
  useContextItems,
  usePipelines,
} from '@/src/lib/queries';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { PipelineRun, Artifact, ContextItem } from '@/src/types';

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const { data: project, isLoading } = useProject(params.id);
  const { data: runs } = useRuns();
  const { data: artifacts } = useArtifacts();
  const { data: context } = useContextItems();
  const { data: pipelines } = usePipelines();

  if (!isLoading && !project) {
    return (
      <Card className="p-10 text-center">
        <p className="text-sm text-muted-foreground">Project “{params.id}” not found.</p>
        <Button asChild variant="link"><Link href="/projects">Back to projects</Link></Button>
      </Card>
    );
  }

  const projectRuns = (runs ?? []).filter((r) => r.projectId === params.id);
  const projectArtifacts = (artifacts ?? []).filter((a) => a.projectId === params.id);
  const projectContext = (context ?? []).filter((c) => c.projectId === params.id);

  const runCols: Column<PipelineRun>[] = [
    { key: 'id', header: 'Run', render: (r) => <span className="font-mono text-xs text-foreground">{r.id}</span> },
    { key: 'pipeline', header: 'Pipeline', render: (r) => <span className="text-foreground">{r.pipeline}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} size="sm" /> },
    { key: 'currentPhase', header: 'Phase', render: (r) => <span className="capitalize text-muted-foreground">{r.currentPhase ?? '—'}</span> },
    { key: 'elapsed', header: 'Elapsed', render: (r) => <span className="text-muted-foreground">{formatDuration(r.elapsedSec)}</span> },
    { key: 'started', header: 'Started', render: (r) => <span className="text-muted-foreground">{formatRelative(r.startedAt)}</span> },
  ];
  const artCols: Column<Artifact>[] = [
    { key: 'name', header: 'Artifact', render: (a) => <span className="font-mono text-foreground">{a.name}</span> },
    { key: 'kind', header: 'Kind', render: (a) => <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] uppercase text-muted-foreground">{a.kind}</span> },
    { key: 'producedBy', header: 'Produced by', render: (a) => <span className="text-muted-foreground">{a.producedBy}</span> },
    { key: 'size', header: 'Size', render: (a) => <span className="text-muted-foreground">{a.sizeKb} KB</span> },
    { key: 'created', header: 'Created', render: (a) => <span className="text-muted-foreground">{formatRelative(a.createdAt)}</span> },
  ];
  const ctxCols: Column<ContextItem>[] = [
    { key: 'key', header: 'Key', render: (c) => <span className="font-mono text-foreground">{c.key}</span> },
    { key: 'scope', header: 'Scope', render: (c) => <span className="capitalize text-muted-foreground">{c.scope}</span> },
    { key: 'type', header: 'Type', render: (c) => <span className="capitalize text-muted-foreground">{c.type}</span> },
    { key: 'summary', header: 'Summary', render: (c) => <span className="line-clamp-1 text-muted-foreground">{c.summary}</span> },
    { key: 'tokens', header: 'Tokens', align: 'right', render: (c) => <span className="text-muted-foreground">{c.tokens.toLocaleString()}</span> },
  ];

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground">
        <Link href="/projects"><ArrowLeft className="h-4 w-4" /> Projects</Link>
      </Button>

      <PageHeader
        title={project?.name ?? params.id}
        eyebrow={project?.slug}
        description={project?.description}
        actions={project ? <StatusBadge status={project.pipelineStatus} /> : null}
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="pipelines">Pipelines</TabsTrigger>
          <TabsTrigger value="runs">Runs ({projectRuns.length})</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts ({projectArtifacts.length})</TabsTrigger>
          <TabsTrigger value="context">Context ({projectContext.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Card className="p-4"><p className="text-xs text-muted-foreground">Environment</p><p className="mt-1 text-lg font-semibold capitalize text-foreground">{project?.environment}</p></Card>
            <Card className="p-4"><p className="text-xs text-muted-foreground">Artifacts</p><p className="mt-1 text-lg font-semibold text-foreground">{project?.artifactCount}</p></Card>
            <Card className="p-4"><p className="text-xs text-muted-foreground">Total runs</p><p className="mt-1 text-lg font-semibold text-foreground">{projectRuns.length}</p></Card>
            <Card className="p-4"><p className="text-xs text-muted-foreground">Last run</p><p className="mt-1 text-lg font-semibold text-foreground">{formatRelative(project?.lastRunAt ?? null)}</p></Card>
          </div>
          <Card className="p-4">
            <div className="flex items-center gap-2 text-sm">
              <GitBranch className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Repository</span>
              <code className="font-mono text-foreground">{project?.repo}</code>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="pipelines" className="space-y-3">
          {(pipelines ?? []).map((p) => (
            <Card key={p.id} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-foreground">{p.name}</p>
                  <p className="text-sm text-muted-foreground">{p.description}</p>
                </div>
                <span className="text-xs text-muted-foreground">{p.phases.length} phases</span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                {p.phases.map((ph, i) => (
                  <span key={i} className="inline-flex items-center gap-1.5">
                    <span className="rounded-md bg-muted px-2 py-1 text-xs capitalize text-foreground">{ph.phase}{ph.hitl ? ' ⚑' : ''}</span>
                    {i < p.phases.length - 1 ? <span className="text-muted-foreground">→</span> : null}
                  </span>
                ))}
              </div>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="runs">
          {projectRuns.length ? <DataTable columns={runCols} rows={projectRuns} getRowId={(r) => r.id} /> : <EmptyState icon={GitBranch} title="No runs yet" description="This project has no pipeline runs." />}
        </TabsContent>
        <TabsContent value="artifacts">
          {projectArtifacts.length ? <DataTable columns={artCols} rows={projectArtifacts} getRowId={(a) => a.id} /> : <EmptyState icon={FileBox} title="No artifacts" description="No deliverables produced yet." />}
        </TabsContent>
        <TabsContent value="context">
          {projectContext.length ? <DataTable columns={ctxCols} rows={projectContext} getRowId={(c) => c.id} /> : <EmptyState icon={Clock} title="No context" description="No shared context for this project." />}
        </TabsContent>
      </Tabs>
    </>
  );
}
