'use client';

import Link from 'next/link';
import { FolderKanban, FileBox, Clock, GitBranch } from 'lucide-react';
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
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-44 w-full rounded-lg" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(projects ?? []).map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="group block">
              <Card className="flex h-full flex-col p-4 transition-colors hover:border-teal-400/60 hover:bg-accent/40">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400">
                      <FolderKanban className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground group-hover:text-teal-600 dark:group-hover:text-teal-400">{p.name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{p.slug}</p>
                    </div>
                  </div>
                  <StatusBadge status={p.pipelineStatus} size="sm" />
                </div>
                <p className="mt-3 line-clamp-2 flex-1 text-sm text-muted-foreground">{p.description}</p>
                <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5"><FileBox className="h-3.5 w-3.5" /> {p.artifactCount} artifacts</span>
                  <span className="inline-flex items-center gap-1.5"><GitBranch className="h-3.5 w-3.5" /> {p.environment}</span>
                  <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {formatRelative(p.lastRunAt)}</span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
