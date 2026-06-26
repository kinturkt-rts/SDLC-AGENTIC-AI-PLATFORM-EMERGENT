'use client';

import Link from 'next/link';
import { ArrowLeft, GitBranch, Flag } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { PipelineFlow } from '@/src/components/flow/PipelineFlow';
import { usePipelines } from '@/src/lib/queries';

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

  const hitlCount = pipeline?.phases.filter((p) => p.hitl).length ?? 0;

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
              <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/10 px-2 py-1 text-amber-600 dark:text-amber-400"><Flag className="h-3 w-3" /> {hitlCount} HITL gates</span>
            </div>
          ) : null
        }
      />

      {isLoading || !pipeline ? (
        <Skeleton className="h-[420px] w-full rounded-lg" />
      ) : (
        <>
          <PipelineFlow pipeline={pipeline} />

          <Card>
            <div className="border-b border-border px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><GitBranch className="h-4 w-4 text-teal-500" /> Phase sequence</h2>
            </div>
            <div className="divide-y divide-border">
              {pipeline.phases.map((ph, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold capitalize text-foreground">{ph.phase}</p>
                    <p className="font-mono text-xs text-muted-foreground">{ph.agent}</p>
                  </div>
                  {ph.hitl ? (
                    <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400"><Flag className="h-3 w-3" /> human approval</span>
                  ) : (
                    <span className="text-[11px] text-muted-foreground">automated</span>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </>
  );
}
