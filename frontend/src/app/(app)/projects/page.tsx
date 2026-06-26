'use client';

import Link from 'next/link';
import { FolderKanban, FileBox, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { useProjects } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';

export default function ProjectsPage() {
  const { data: projects, isLoading } = useProjects();

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Projects"
        description="Target applications under management. Each project runs through the SDLC pipeline to produce deliverables."
      />

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-44 w-full rounded-xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(projects ?? []).map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="group block">
              <Card className="flex h-full flex-col overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:border-teal-500/30 hover:bg-card hover:shadow-lg">
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
                <p className="mt-3 line-clamp-2 flex-1 text-[13px] leading-relaxed text-muted-foreground">{p.description}</p>
                <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5"><FileBox className="h-3.5 w-3.5" /> {p.artifactCount} artifacts</span>
                  <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {formatRelative(p.lastRunAt)}</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <p className="rounded-lg border border-dashed border-white/[0.08] bg-card/30 px-4 py-3 text-xs text-muted-foreground">
        New projects appear automatically when an SDLC pipeline run creates{' '}
        <code className="rounded bg-muted/50 px-1 py-0.5 font-mono text-foreground">agents/pipeline/&lt;slug&gt;.context.json</code>.
      </p>
    </>
  );
}
