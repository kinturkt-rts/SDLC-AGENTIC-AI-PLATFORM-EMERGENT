'use client';

import Link from 'next/link';
import { ArrowLeft, GitBranch, FileBox } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { OpenLiveAppLink } from '@/src/components/common/OpenLiveAppLink';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { EmptyState } from '@/src/components/common/EmptyState';
import { ContextView } from '@/src/features/context/ContextView';
import { ProjectRepositoryLink } from '@/src/features/projects/ProjectRepositoryLink';
import {
  useProject,
  useRuns,
  useArtifacts,
  useContextItems,
  usePipelineContext,
} from '@/src/lib/queries';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { PipelineRun, Artifact } from '@/src/types';

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const { data: project, isLoading } = useProject(params.id);
  const { data: runs } = useRuns();
  const { data: artifacts } = useArtifacts();
  // Scope both context queries to this project so the tab badge matches what
  // ContextView renders instead of counting a slower all-projects fetch.
  const { data: context, isLoading: contextLoading } = useContextItems(params.id);
  const { data: pipelineContext, isLoading: pipelineContextLoading } = usePipelineContext(params.id);

  if (!isLoading && !project) {
    return (
      <Card className="border-white/[0.06] bg-card/80 p-10 text-center">
        <p className="text-sm text-muted-foreground">Project "{params.id}" not found.</p>
        <Button asChild variant="link"><Link href="/projects">Back to projects</Link></Button>
      </Card>
    );
  }

  const projectRuns = (runs ?? [])
    .filter((r) => r.projectId === params.id)
    .slice()
    .sort((a, b) => (b.finishedAt ?? b.startedAt).localeCompare(a.finishedAt ?? a.startedAt));
  const projectArtifacts = (artifacts ?? []).filter((a) => a.projectId === params.id);
  const projectContext = (context ?? []).filter((c) => c.projectId === params.id);
  const contextPending = contextLoading || pipelineContextLoading;
  const contextCount = projectContext.length + (pipelineContext ? 1 : 0);
  const latestRun = projectRuns[0];
  const headerStatus = latestRun?.status ?? project?.pipelineStatus;

  const runCols: Column<PipelineRun>[] = [
    { key: 'id', header: 'Run', render: (r) => <span className="font-mono text-xs text-foreground">{r.id}</span> },
    { key: 'pipeline', header: 'Pipeline', render: (r) => <span className="text-foreground">{r.pipeline}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} size="sm" /> },
    { key: 'currentPhase', header: 'Phase', render: (r) => <span className="capitalize text-muted-foreground">{r.currentPhase ?? '\u2014'}</span> },
    { key: 'elapsed', header: 'Elapsed', render: (r) => <span className="text-muted-foreground">{formatDuration(r.elapsedSec)}</span> },
    { key: 'started', header: 'Started', render: (r) => <span className="text-muted-foreground">{formatRelative(r.startedAt)}</span> },
  ];
  const artCols: Column<Artifact>[] = [
    { key: 'name', header: 'Artifact', render: (a) => <span className="font-mono text-foreground">{a.name}</span> },
    { key: 'kind', header: 'Kind', render: (a) => <span className="rounded-md bg-muted/50 px-1.5 py-0.5 text-[11px] uppercase text-muted-foreground">{a.kind}</span> },
    { key: 'producedBy', header: 'Produced by', render: (a) => <span className="text-muted-foreground">{a.producedBy}</span> },
    { key: 'size', header: 'Size', render: (a) => <span className="text-muted-foreground">{a.sizeKb} KB</span> },
    { key: 'created', header: 'Created', render: (a) => <span className="text-muted-foreground">{formatRelative(a.createdAt)}</span> },
  ];

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground hover:text-foreground">
        <Link href="/projects"><ArrowLeft className="h-4 w-4" /> Projects</Link>
      </Button>

      <PageHeader
        title={project?.name ?? params.id}
        eyebrow={project?.slug}
        description={project?.description}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {project?.liveUrl ? <OpenLiveAppLink href={project.liveUrl} variant="button" /> : null}
            {headerStatus ? <StatusBadge status={headerStatus} /> : null}
          </div>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList className="border-white/[0.06] bg-muted/40">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="runs">Runs ({projectRuns.length})</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts ({projectArtifacts.length})</TabsTrigger>
          <TabsTrigger value="context">Context{contextPending ? '' : ` (${contextCount})`}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            <Card className="border-white/[0.06] bg-card/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Artifacts</p>
              <p className="mt-1.5 text-2xl font-bold text-foreground">{project?.artifactCount}</p>
            </Card>
            <Card className="border-white/[0.06] bg-card/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Total Runs</p>
              <p className="mt-1.5 text-2xl font-bold text-foreground">{projectRuns.length}</p>
            </Card>
            <Card className="border-white/[0.06] bg-card/80 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Last Run</p>
              <p className="mt-1.5 text-2xl font-bold text-foreground">{formatRelative(project?.lastRunAt ?? null)}</p>
            </Card>
          </div>
          <Card className="border-white/[0.06] bg-card/80 p-4">
            {project ? <ProjectRepositoryLink project={project} /> : null}
            {project?.liveUrl ? (
              <div className="mt-3 border-t border-white/[0.06] pt-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  Deploy
                </p>
                <OpenLiveAppLink href={project.liveUrl} className="mt-1.5" />
              </div>
            ) : null}
          </Card>
        </TabsContent>

        <TabsContent value="runs">
          {projectRuns.length ? <DataTable columns={runCols} rows={projectRuns} getRowId={(r) => r.id} /> : <EmptyState icon={GitBranch} title="No runs yet" description="This project has no pipeline runs." />}
        </TabsContent>
        <TabsContent value="artifacts">
          {projectArtifacts.length ? <DataTable columns={artCols} rows={projectArtifacts} getRowId={(a) => a.id} /> : <EmptyState icon={FileBox} title="No artifacts" description="No deliverables produced yet." />}
        </TabsContent>
        <TabsContent value="context">
          <ContextView projectSlug={params.id} />
        </TabsContent>
      </Tabs>
    </>
  );
}