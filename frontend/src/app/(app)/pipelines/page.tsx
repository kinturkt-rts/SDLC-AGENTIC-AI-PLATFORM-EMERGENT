'use client';

import { GitBranch, ChevronRight, ArrowRight, Zap } from 'lucide-react';
import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { usePipelines } from '@/src/lib/queries';
import { phaseDisplayLabel } from '@/src/lib/pipeline-phases';

export default function PipelinesPage() {
  const { data: pipelines, isLoading } = usePipelines();

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Pipelines"
        description="The live MVP delivery path. Each phase is run by a specialist AgentCore agent - start a run from the Dashboard."
      />

      {isLoading ? (
        <div className="space-y-4">{Array.from({ length: 1 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)}</div>
      ) : (
        <div className="space-y-4">
          {(pipelines ?? []).map((p) => (
            <Link key={p.id} href={`/pipelines/${p.id}`} className="group block">
              <Card className="overflow-hidden border-white/[0.06] bg-card/80 p-5 transition-all duration-300 hover:border-teal-500/30 hover:bg-card hover:shadow-lg">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 ring-1 ring-inset ring-teal-500/20">
                      <GitBranch className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-foreground">{p.name}</p>
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium text-emerald-400">
                          <Zap className="h-2.5 w-2.5" /> Fully automated
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">{p.description}</p>
                    </div>
                  </div>
                  <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-teal-400">
                    View graph <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>

                <div className="mt-5 flex flex-wrap items-stretch gap-2">
                  {p.phases.map((ph, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="min-w-[140px] rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 transition-colors group-hover:border-white/[0.1]">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                          {`Phase ${i + 1}`}
                        </span>
                        <p className="mt-1 text-sm font-semibold text-foreground">{phaseDisplayLabel(ph.phase)}</p>
                        <p className="font-mono text-xs text-muted-foreground">{ph.agent}</p>
                      </div>
                      {i < p.phases.length - 1 ? (
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/30" aria-hidden />
                      ) : null}
                    </div>
                  ))}
                </div>

                <p className="mt-4 text-xs text-muted-foreground">
                  Start a brief on the{' '}
                  <span className="font-medium text-foreground">Dashboard</span> to run this pipeline.
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
