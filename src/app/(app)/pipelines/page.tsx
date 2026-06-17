'use client';

import { GitBranch, Flag } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { usePipelines } from '@/src/lib/queries';

export default function PipelinesPage() {
  const { data: pipelines, isLoading } = usePipelines();

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Pipelines"
        description="Reusable SDLC pipeline definitions. Each phase is executed by a specialist agent; flagged phases require human approval."
      />

      {isLoading ? (
        <div className="space-y-4">{Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-lg" />)}</div>
      ) : (
        <div className="space-y-4">
          {(pipelines ?? []).map((p) => (
            <Card key={p.id} className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-teal-500/10 text-teal-600 dark:text-teal-400">
                    <GitBranch className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{p.name}</p>
                    <p className="text-sm text-muted-foreground">{p.description}</p>
                  </div>
                </div>
                <span className="shrink-0 text-xs text-muted-foreground">{p.phases.length} phases</span>
              </div>

              <div className="mt-5 flex flex-wrap items-stretch gap-2">
                {p.phases.map((ph, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="min-w-[150px] rounded-lg border border-border bg-card p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{`Phase ${i + 1}`}</span>
                        {ph.hitl ? (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400"><Flag className="h-2.5 w-2.5" /> HITL</span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-sm font-semibold capitalize text-foreground">{ph.phase}</p>
                      <p className="font-mono text-xs text-muted-foreground">{ph.agent}</p>
                    </div>
                    {i < p.phases.length - 1 ? <span className="text-lg text-muted-foreground">→</span> : null}
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
