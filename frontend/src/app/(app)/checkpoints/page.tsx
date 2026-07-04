'use client';

import * as React from 'react';
import { Check, X, UserCheck, ShieldQuestion } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useCheckpoints, useProjects } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative } from '@/src/lib/format';
import type { HITLCheckpoint } from '@/src/types';

export default function CheckpointsPage() {
  const { data: checkpoints, isLoading } = useCheckpoints();
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const [overrides, setOverrides] = React.useState<Record<string, HITLCheckpoint['status']>>({});

  const projectName = projects?.find((p) => p.id === currentProjectId)?.name ?? currentProjectId;

  const resolve = (c: HITLCheckpoint, status: 'approved' | 'rejected') => {
    setOverrides((o) => ({ ...o, [c.id]: status }));
    toast.success(`Checkpoint ${status}`, {
      description: `${c.title} \u2014 recorded locally (control plane has no platform API yet).`,
    });
  };

  const items = (checkpoints ?? [])
    .filter((c) => c.projectId === currentProjectId)
    .map((c) => ({ ...c, status: overrides[c.id] ?? c.status }));
  const pending = items.filter((c) => c.status === 'pending');
  const resolved = items.filter((c) => c.status !== 'pending');

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="HITL Checkpoints"
        description={`Human-in-the-loop gates for ${projectName} — approve, reject, or clarify before the pipeline continues.`}
      />

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}</div>
      ) : (
        <>
          <div>
            <div className="mb-3 flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-amber-400" />
              <h2 className="text-sm font-semibold text-foreground">Pending</h2>
              <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">{pending.length}</span>
            </div>
            {pending.length === 0 ? (
              <EmptyState icon={UserCheck} title="All clear" description="No checkpoints are waiting for human review." />
            ) : (
              <div className="space-y-3">
                {pending.map((c) => (
                  <Card key={c.id} className="border-amber-500/20 bg-amber-500/[0.03] p-4 transition-colors hover:bg-amber-500/[0.06]">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={c.status} size="sm" />
                          <span className="text-xs capitalize text-muted-foreground">{c.phase} \u00b7 {c.agent}</span>
                        </div>
                        <p className="mt-2 font-medium text-foreground">{c.title}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{c.description}</p>
                        <p className="mt-2 font-mono text-xs text-muted-foreground">{c.projectName} \u00b7 {c.runId} \u00b7 {formatRelative(c.requestedAt)}</p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="gap-1.5 border-white/[0.08]" onClick={() => resolve(c, 'rejected')}><X className="h-4 w-4" /> Reject</Button>
                        <Button size="sm" className="gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700" onClick={() => resolve(c, 'approved')}><Check className="h-4 w-4" /> Approve</Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <ShieldQuestion className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Resolved</h2>
              <span className="rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">{resolved.length}</span>
            </div>
            <div className="space-y-2">
              {resolved.map((c) => (
                <Card key={c.id} className="flex items-center justify-between border-white/[0.06] bg-card/80 p-3 transition-colors hover:bg-white/[0.02]">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">{c.projectName} \u00b7 {c.approver ? `by ${c.approver}` : 'auto'} \u00b7 {formatRelative(c.requestedAt)}</p>
                  </div>
                  <StatusBadge status={c.status} size="sm" />
                </Card>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  );
}
