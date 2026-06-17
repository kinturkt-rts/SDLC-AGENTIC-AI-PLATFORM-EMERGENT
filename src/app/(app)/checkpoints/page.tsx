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
import { useCheckpoints } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { HITLCheckpoint } from '@/src/types';

export default function CheckpointsPage() {
  const { data: checkpoints, isLoading } = useCheckpoints();
  const [overrides, setOverrides] = React.useState<Record<string, HITLCheckpoint['status']>>({});

  const resolve = (c: HITLCheckpoint, status: 'approved' | 'rejected') => {
    setOverrides((o) => ({ ...o, [c.id]: status }));
    toast.success(`Checkpoint ${status}`, {
      description: `${c.title} — recorded locally (control plane has no platform API yet).`,
    });
  };

  const items = (checkpoints ?? []).map((c) => ({ ...c, status: overrides[c.id] ?? c.status }));
  const pending = items.filter((c) => c.status === 'pending');
  const resolved = items.filter((c) => c.status !== 'pending');

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="HITL Checkpoints"
        description="Human-in-the-loop gates where the pipeline pauses for a person to approve, reject, or clarify."
      />

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-lg" />)}</div>
      ) : (
        <>
          <div>
            <div className="mb-2 flex items-center gap-2">
              <UserCheck className="h-4 w-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-foreground">Pending ({pending.length})</h2>
            </div>
            {pending.length === 0 ? (
              <EmptyState icon={UserCheck} title="All clear" description="No checkpoints are waiting for human review." />
            ) : (
              <div className="space-y-3">
                {pending.map((c) => (
                  <Card key={c.id} className="p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <StatusBadge status={c.status} size="sm" />
                          <span className="text-xs capitalize text-muted-foreground">{c.phase} · {c.agent}</span>
                        </div>
                        <p className="mt-2 font-medium text-foreground">{c.title}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{c.description}</p>
                        <p className="mt-2 font-mono text-xs text-muted-foreground">{c.projectName} · {c.runId} · {formatRelative(c.requestedAt)}</p>
                      </div>
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => resolve(c, 'rejected')}><X className="h-4 w-4" /> Reject</Button>
                        <Button size="sm" className="gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700" onClick={() => resolve(c, 'approved')}><Check className="h-4 w-4" /> Approve</Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2">
              <ShieldQuestion className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Resolved ({resolved.length})</h2>
            </div>
            <div className="space-y-2">
              {resolved.map((c) => (
                <Card key={c.id} className="flex items-center justify-between p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{c.title}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">{c.projectName} · {c.approver ? `by ${c.approver}` : 'auto'} · {formatRelative(c.requestedAt)}</p>
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
