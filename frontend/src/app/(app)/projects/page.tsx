'use client';

import * as React from 'react';
import Link from 'next/link';
import { FolderKanban, FileBox, Clock, Workflow, Activity, ArrowRight } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { LiveRelative } from '@/src/components/common/LiveElapsed';
import { OpenLiveAppLink } from '@/src/components/common/OpenLiveAppLink';
import { useProjects, useRuns } from '@/src/lib/queries';
import type { PipelineRun, Project, RunStatus } from '@/src/types';

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

function runActivityIso(run: PipelineRun): string {
  return run.finishedAt ?? run.startedAt;
}

/** Prefer the newest reconciled run status over the projects API badge. */
function projectLiveView(
  project: Project,
  latestRun: PipelineRun | undefined,
): { status: RunStatus; lastRunAt: string } {
  if (!latestRun) {
    return { status: project.pipelineStatus, lastRunAt: project.lastRunAt };
  }
  return {
    status: latestRun.status,
    lastRunAt: runActivityIso(latestRun),
  };
}

export default function ProjectsPage() {
  const { data: projects, isLoading, isError, error } = useProjects();
  const { data: runs } = useRuns();

  const runsByProject = React.useMemo(() => {
    const counts = new Map<string, number>();
    const latest = new Map<string, PipelineRun>();
    for (const run of runs ?? []) {
      counts.set(run.projectId, (counts.get(run.projectId) ?? 0) + 1);
      const prev = latest.get(run.projectId);
      if (!prev || runActivityIso(run).localeCompare(runActivityIso(prev)) > 0) {
        latest.set(run.projectId, run);
      }
    }
    return { counts, latest };
  }, [runs]);

  const sortedProjects = React.useMemo(() => {
    return [...(projects ?? [])].sort((a, b) => {
      const aLive = projectLiveView(a, runsByProject.latest.get(a.id));
      const bLive = projectLiveView(b, runsByProject.latest.get(b.id));
      return bLive.lastRunAt.localeCompare(aLive.lastRunAt);
    });
  }, [projects, runsByProject.latest]);

  const activeRunCount = (runs ?? []).filter((r) => r.status === 'running' || r.status === 'paused').length;
  const totalArtifacts = sortedProjects.reduce((sum, p) => sum + p.artifactCount, 0);

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Projects"
        description="Target applications produced by the SDLC pipeline - PRDs, diagrams, designs, SQL, Python code, and live AWS deploys. Status refreshes from the latest pipeline run."
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
            {sortedProjects.map((p) => {
              const latestRun = runsByProject.latest.get(p.id);
              const live = projectLiveView(p, latestRun);
              const runCount = runsByProject.counts.get(p.id) ?? 0;
              const isLive = live.status === 'running' || live.status === 'paused';
              return (
                <Card
                  key={p.id}
                  className="group relative flex h-full flex-col overflow-hidden border-white/[0.06] bg-card/80 transition-all duration-300 hover:border-teal-500/30 hover:bg-card hover:shadow-lg"
                >
                  <div className="absolute left-0 top-0 h-[2px] w-full bg-gradient-to-r from-teal-500 to-cyan-400 opacity-0 transition-opacity group-hover:opacity-60" />
                  <Link href={`/projects/${p.id}`} className="flex flex-1 flex-col p-4 pb-3">
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
                      <StatusBadge status={live.status} size="sm" />
                    </div>
                    <p className="mt-3 line-clamp-2 flex-1 text-[13px] leading-relaxed text-muted-foreground">
                      {p.description || 'No description - open project for pipeline context and artifacts.'}
                    </p>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] pt-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1.5">
                        <Workflow className="h-3.5 w-3.5" />
                        {runCount} run{runCount === 1 ? '' : 's'}
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <FileBox className="h-3.5 w-3.5" /> {p.artifactCount} artifacts
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        <LiveRelative iso={live.lastRunAt} live={isLive} />
                      </span>
                    </div>
                  </Link>
                  {p.liveUrl ? (
                    <div className="border-t border-white/[0.06] px-4 py-2.5">
                      <OpenLiveAppLink href={p.liveUrl} variant="chip" />
                    </div>
                  ) : null}
                </Card>
              );
            })}
          </div>

          <p className="text-center text-[11px] text-muted-foreground/80">
            Status comes from the latest reconciled pipeline run (refreshes about every 15s). Artifacts are counted from
            S3/<code className="rounded bg-muted/40 px-1">backend/target-apps/</code>.
          </p>
        </div>
      )}
    </>
  );
}
