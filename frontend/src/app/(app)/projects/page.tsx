'use client';

import * as React from 'react';
import Link from 'next/link';
import { FolderKanban, FileBox, Clock, Workflow, Activity, ArrowRight } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useProjects, useRuns } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';

function StatPill({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  icon: typeof FolderKanban;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-card/60 px-3 py-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-teal-500/10 text-teal-400">
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div>
        <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold text-foreground">{value}</p>
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const { data: projects, isLoading, isError, error } = useProjects();
  const { data: runs } = useRuns();

  const runCountByProject = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const run of runs ?? []) {
      counts.set(run.projectId, (counts.get(run.projectId) ?? 0) + 1);
    }
    return counts;
  }, [runs]);

  const sortedProjects = React.useMemo(
    () => [...(projects ?? [])].sort((a, b) => b.lastRunAt.localeCompare(a.lastRunAt)),
    [projects],
  );

  const activeRunCount = (runs ?? []).filter((r) => r.status === 'running' || r.status === 'paused').length;
  const totalArtifacts = sortedProjects.reduce((sum, p) => sum + p.artifactCount, 0);

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Projects"
        description="Target applications produced by the SDLC pipeline — PRDs, designs, SQL, and FastAPI code. Each slug is a feature app under backend/target-apps/."
        actions={
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1 text-xs font-medium text-teal-400 hover:underline"
          >
            Submit a brief <ArrowRight className="h-3 w-3" />
          </Link>
        }
      />

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-lg" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-44 w-full rounded-xl" />
            ))}
          </div>
        </div>
      ) : isError ? (
        <EmptyState
          icon={FolderKanban}
          title="Could not load projects"
          description={
            error instanceof Error
              ? `${error.message}. If you use S3 artifact storage, run \`aws sso login\` and restart the dev server.`
              : 'The projects API failed. Check the terminal running npm run dev for details.'
          }
          action={
            <Link href="/dashboard" className="text-sm font-medium text-teal-400 hover:underline">
              Go to Dashboard
            </Link>
          }
        />
      ) : sortedProjects.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Submit a requirements brief from the Dashboard to start your first pipeline run. Projects appear here once context files or target-apps exist under backend/."
          action={
            <Link href="/dashboard" className="text-sm font-medium text-teal-400 hover:underline">
              Submit a brief from Dashboard
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatPill label="Projects" value={sortedProjects.length} icon={FolderKanban} />
            <StatPill label="Pipeline runs" value={runs?.length ?? 0} icon={Workflow} />
            <StatPill label="Active now" value={activeRunCount} icon={Activity} />
            <StatPill label="Artifacts" value={totalArtifacts} icon={FileBox} />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {sortedProjects.map((p) => (
              <Link key={p.id} href={`/projects/${p.id}`} className="group block">
                <Card className="relative flex h-full flex-col overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:border-teal-500/30 hover:bg-card hover:shadow-lg">
                  <div className="absolute left-0 top-0 h-[2px] w-full bg-gradient-to-r from-teal-500 to-cyan-400 opacity-0 transition-opacity group-hover:opacity-60" />
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 ring-1 ring-inset ring-teal-500/20">
                        <FolderKanban className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="font-semibold text-foreground">{p.name}</p>
                        <p className="font-mono text-xs text-muted-foreground">{p.slug}</p>
                      </div>
                    </div>
                    <StatusBadge status={p.pipelineStatus} size="sm" />
                  </div>
                  <p className="mt-3 line-clamp-2 flex-1 text-[13px] leading-relaxed text-muted-foreground">
                    {p.description || 'No description — open project for pipeline context and artifacts.'}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] pt-3 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1.5">
                      <Workflow className="h-3.5 w-3.5" />
                      {runCountByProject.get(p.id) ?? 0} run
                      {(runCountByProject.get(p.id) ?? 0) === 1 ? '' : 's'}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <FileBox className="h-3.5 w-3.5" /> {p.artifactCount} artifacts
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" /> {formatRelative(p.lastRunAt)}
                    </span>
                  </div>
                </Card>
              </Link>
            ))}
          </div>

          <p className="text-center text-[11px] text-muted-foreground/80">
            Data is read from your monorepo (
            <code className="rounded bg-muted/40 px-1">backend/target-apps/</code>,{' '}
            <code className="rounded bg-muted/40 px-1">backend/agents/pipeline/*.context.json</code>
            ) or S3 when <code className="rounded bg-muted/40 px-1">ARTIFACT_STORE=s3</code>.
          </p>
        </div>
      )}
    </>
  );
}
