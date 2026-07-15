'use client';

import Link from 'next/link';
import { ArrowLeft, GitBranch, Zap, FileText, Building2, Database, Code2 } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { PipelineFlow } from '@/src/components/flow/PipelineFlow';
import { usePipelines } from '@/src/lib/queries';
import { phaseDisplayLabel } from '@/src/lib/pipeline-phases';
import type { SdlcPhase } from '@/src/types';

const PHASE_OUTPUT: Partial<Record<SdlcPhase, { icon: typeof FileText; output: string }>> = {
  requirements: { icon: FileText, output: 'PRD markdown in docs/PRD/' },
  architecture: { icon: Building2, output: 'Solution design + architecture diagram' },
  data: { icon: Database, output: 'SQL migrations and DB handoff' },
  implementation: { icon: Code2, output: 'FastAPI app, tests, and README' },
  deploy: { icon: GitBranch, output: 'Publish to GitLab branch sdlc/<app>' },
};

export default function PipelineDetailPage({ params }: { params: { id: string } }) {
  const { data: pipelines, isLoading } = usePipelines();
  const pipeline = pipelines?.find((p) => p.id === params.id);

  if (!isLoading && !pipeline) {
    return (
      <Card className="p-10 text-center">
        <p className="text-sm text-muted-foreground">Pipeline &ldquo;{params.id}&rdquo; not found.</p>
        <Button asChild variant="link"><Link href="/pipelines">Back to pipelines</Link></Button>
      </Card>
    );
  }

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground">
        <Link href="/pipelines"><ArrowLeft className="h-4 w-4" /> Pipelines</Link>
      </Button>

      <PageHeader
        eyebrow="Design"
        title={pipeline?.name ?? params.id}
        description={pipeline?.description}
        actions={
          pipeline ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-md bg-muted px-2 py-1">{pipeline.phases.length} phases</span>
              <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-emerald-400">
                <Zap className="h-3 w-3" /> Fully automated
              </span>
            </div>
          ) : null
        }
      />

      {isLoading || !pipeline ? (
        <Skeleton className="h-[280px] w-full rounded-lg" />
      ) : (
        <>
          <PipelineFlow pipeline={pipeline} />

          <Card className="mt-4">
            <div className="border-b border-border px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <GitBranch className="h-4 w-4 text-teal-500" /> What each phase produces
              </h2>
            </div>
            <div className="divide-y divide-border">
              {pipeline.phases.map((ph, i) => {
                const meta = PHASE_OUTPUT[ph.phase];
                const Icon = meta?.icon ?? FileText;
                return (
                  <div key={i} className="flex items-center gap-3 px-4 py-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground">{phaseDisplayLabel(ph.phase)}</p>
                      <p className="font-mono text-xs text-muted-foreground">{ph.agent}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{meta?.output ?? 'Pipeline artifact'}</p>
                    </div>
                    <span className="text-[11px] text-muted-foreground">automated</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </>
      )}
    </>
  );
}