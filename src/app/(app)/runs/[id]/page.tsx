'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Workflow,
  PauseCircle,
  PlayCircle,
  XCircle,
  CheckCircle2,
  Loader2,
  Clock,
  MinusCircle,
  UserCheck,
  Bot,
  FileBox,
  Radio,
  Check,
  X,
  Send,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useRun, useRunEvents, useArtifacts, useCheckpoints } from '@/src/lib/queries';
import { api } from '@/src/lib/api';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { RunStatus, StepStatus, PipelineStep, RunEvent } from '@/src/types';

const STEP_ICON: Record<StepStatus, typeof Clock> = {
  queued: Clock,
  running: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  waiting_for_human: UserCheck,
  skipped: MinusCircle,
};

const STEP_ICON_COLOR: Record<StepStatus, string> = {
  queued: 'text-slate-400',
  running: 'text-blue-500',
  completed: 'text-emerald-500',
  failed: 'text-red-500',
  waiting_for_human: 'text-amber-500',
  skipped: 'text-slate-400',
};

function EventRow({
  icon: Icon,
  color,
  ts,
  title,
  detail,
}: {
  icon: typeof Clock;
  color: string;
  ts: string;
  title: React.ReactNode;
  detail: string;
}) {
  return (
    <div className="border-b border-border/60 px-2 py-2 last:border-0">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-3.5 w-3.5 shrink-0', color)} />
        <span className="truncate text-foreground">{title}</span>
        <span className="ml-auto shrink-0 text-muted-foreground">{formatRelative(ts)}</span>
      </div>
      <p className="mt-1 pl-5 text-muted-foreground">{detail}</p>
    </div>
  );
}

// Renders a single discriminated RunEvent. TypeScript narrows per `kind`.
function RunEventItem({ event }: { event: RunEvent }) {
  switch (event.kind) {
    case 'log':
      return (
        <div className="border-b border-border/60 px-2 py-2 last:border-0">
          <div className="flex items-center gap-2">
            <StatusBadge status={event.level} size="sm" />
            <span className="truncate text-teal-600 dark:text-teal-400">{event.agent}</span>
            <span className="ml-auto shrink-0 text-muted-foreground">{formatRelative(event.ts)}</span>
          </div>
          <p className="mt-1 pl-1 text-foreground">{event.message}</p>
        </div>
      );
    case 'phase.started':
      return <EventRow icon={PlayCircle} color="text-blue-500" ts={event.ts} title={<>Phase <span className="capitalize">{event.phase}</span> started</>} detail={event.agent} />;
    case 'phase.completed':
      return <EventRow icon={CheckCircle2} color="text-emerald-500" ts={event.ts} title={<>Phase <span className="capitalize">{event.phase}</span> completed</>} detail={`${event.agent} · ${formatDuration(event.durationSec)}`} />;
    case 'step.failed':
      return <EventRow icon={XCircle} color="text-red-500" ts={event.ts} title={<>Step failed at <span className="capitalize">{event.phase}</span></>} detail={event.error} />;
    case 'hitl.requested':
      return <EventRow icon={UserCheck} color="text-amber-500" ts={event.ts} title="HITL requested" detail={event.title} />;
    case 'artifact.created':
      return <EventRow icon={FileBox} color="text-teal-500" ts={event.ts} title={<>Artifact <span className="font-medium">{event.artifactName}</span></>} detail={`${event.artifactKind} · ${event.agent}`} />;
    case 'agent.message':
      return <EventRow icon={Send} color="text-blue-500" ts={event.ts} title={<><span className="font-mono">{event.messageType}</span> · {event.from} → {event.to}</>} detail={event.summary} />;
    default:
      return null;
  }
}

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const { data: run, isLoading } = useRun(params.id);
  const { data: events } = useRunEvents(params.id);
  const { data: artifacts } = useArtifacts();
  const { data: checkpoints } = useCheckpoints();

  const [statusOverride, setStatusOverride] = React.useState<RunStatus | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [hitlOverride, setHitlOverride] = React.useState<Record<string, 'approved' | 'rejected'>>({});

  if (!isLoading && !run) {
    return (
      <Card className="p-10 text-center">
        <p className="text-sm text-muted-foreground">Run &ldquo;{params.id}&rdquo; not found.</p>
        <Button asChild variant="link"><Link href="/runs">Back to runs</Link></Button>
      </Card>
    );
  }

  const status: RunStatus = statusOverride ?? run?.status ?? 'queued';
  const runArtifacts = (artifacts ?? []).filter((a) => a.runId === params.id);
  const runCheckpoints = (checkpoints ?? [])
    .filter((c) => c.runId === params.id)
    .map((c) => ({ ...c, status: hitlOverride[c.id] ?? c.status }));
  const waitingStep = run?.steps.find((s) => s.status === 'waiting_for_human') ?? null;
  const runEvents = [...(events ?? [])].sort((a, b) => +new Date(b.ts) - +new Date(a.ts));
  const isLive = status === 'running';

  const control = async (action: 'pause' | 'resume' | 'cancel') => {
    setBusy(action);
    const res = await api.controlRun(params.id, action);
    setStatusOverride(res.status);
    setBusy(null);
    toast.success(`Run ${action}d`, {
      description: `${params.id} → ${res.status} (control-plane action, mock — no agents executed).`,
    });
  };

  const resolveHitl = (id: string, title: string, decision: 'approved' | 'rejected') => {
    setHitlOverride((o) => ({ ...o, [id]: decision }));
    toast.success(`Checkpoint ${decision}`, { description: `${title} — recorded locally (mock).` });
  };

  const controls = (
    <div className="flex items-center gap-2">
      {status === 'running' && (
        <Button size="sm" variant="outline" className="gap-1.5" disabled={!!busy} onClick={() => control('pause')}>
          {busy === 'pause' ? <Loader2 className="h-4 w-4 animate-spin" /> : <PauseCircle className="h-4 w-4" />} Pause
        </Button>
      )}
      {status === 'paused' && (
        <Button size="sm" className="gap-1.5 bg-blue-600 text-white hover:bg-blue-700" disabled={!!busy} onClick={() => control('resume')}>
          {busy === 'resume' ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />} Resume
        </Button>
      )}
      {(status === 'running' || status === 'paused' || status === 'queued') && (
        <Button size="sm" variant="outline" className="gap-1.5 text-red-600 hover:text-red-700" disabled={!!busy} onClick={() => control('cancel')}>
          {busy === 'cancel' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />} Cancel
        </Button>
      )}
      <StatusBadge status={status} />
    </div>
  );

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground">
        <Link href="/runs"><ArrowLeft className="h-4 w-4" /> Pipeline Runs</Link>
      </Button>

      <PageHeader
        eyebrow={run ? `${run.id} · ${run.pipeline}` : params.id}
        title={run?.projectName ?? params.id}
        description={run ? `Triggered by ${run.triggeredBy} · started ${formatRelative(run.startedAt)} · elapsed ${formatDuration(run.elapsedSec)}` : undefined}
        actions={isLoading ? null : controls}
      />

      {isLoading || !run ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="h-96 w-full rounded-lg lg:col-span-2" />
          <Skeleton className="h-96 w-full rounded-lg" />
        </div>
      ) : (
        <>
          {/* Active agent banner */}
          {status === 'running' && run.currentAgent ? (
            <Card className="flex items-center gap-3 border-blue-200/60 bg-blue-50/50 p-4 dark:border-blue-900/50 dark:bg-blue-950/20">
              <span className="relative flex h-8 w-8 items-center justify-center rounded-md bg-blue-500/15 text-blue-600 dark:text-blue-400">
                <Bot className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  <span className="font-mono">{run.currentAgent}</span> is executing the <span className="capitalize">{run.currentPhase}</span> phase
                </p>
                <p className="text-xs text-muted-foreground">Live status from the platform — the control plane does not run the agent.</p>
              </div>
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            </Card>
          ) : null}

          {/* Inline HITL when waiting for a human */}
          {waitingStep ? (
            (() => {
              const cp = runCheckpoints.find((c) => c.status === 'pending');
              return (
                <Card className="border-amber-200/70 bg-amber-50/50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      <UserCheck className="mt-0.5 h-5 w-5 text-amber-500" />
                      <div>
                        <p className="text-sm font-semibold text-foreground">{cp?.title ?? `Human approval required at ${waitingStep.phase}`}</p>
                        <p className="text-xs text-muted-foreground">{cp?.description ?? `The ${waitingStep.agent} paused this run for human review.`}</p>
                      </div>
                    </div>
                    {cp ? (
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => resolveHitl(cp.id, cp.title, 'rejected')}><X className="h-4 w-4" /> Reject</Button>
                        <Button size="sm" className="gap-1.5 bg-emerald-600 text-white hover:bg-emerald-700" onClick={() => resolveHitl(cp.id, cp.title, 'approved')}><Check className="h-4 w-4" /> Approve</Button>
                      </div>
                    ) : null}
                  </div>
                </Card>
              );
            })()
          ) : null}

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Phase stepper / timeline */}
            <Card className="lg:col-span-2">
              <div className="border-b border-border px-4 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Workflow className="h-4 w-4 text-teal-500" /> SDLC phase timeline</h2>
              </div>
              <ol className="p-4">
                {run.steps.map((step: PipelineStep, i: number) => {
                  const Icon = STEP_ICON[step.status];
                  const last = i === run.steps.length - 1;
                  const active = step.status === 'running' || step.status === 'waiting_for_human';
                  return (
                    <li key={step.id} className="relative flex gap-4 pb-6 last:pb-0">
                      {!last ? <span className="absolute left-[15px] top-8 h-[calc(100%-1rem)] w-px bg-border" /> : null}
                      <span className={cn('relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border bg-card', STEP_ICON_COLOR[step.status])}>
                        <Icon className={cn('h-4 w-4', step.status === 'running' && 'animate-spin')} />
                      </span>
                      <div className={cn('min-w-0 flex-1 rounded-md border p-3', active ? 'border-blue-200/60 bg-blue-50/40 dark:border-blue-900/50 dark:bg-blue-950/20' : 'border-transparent')}>
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold capitalize text-foreground">{step.phase}</p>
                          <StatusBadge status={step.status} size="sm" />
                        </div>
                        <p className="font-mono text-xs text-muted-foreground">{step.agent}</p>
                        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                          {step.startedAt ? <span>started {formatRelative(step.startedAt)}</span> : <span>not started</span>}
                          {step.durationSec != null ? <span>· {formatDuration(step.durationSec)}</span> : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </Card>

            {/* Per-run event stream (SSE-ready) */}
            <Card className="flex flex-col">
              <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Radio className="h-4 w-4 text-teal-500" /> Event stream</h2>
                {isLive ? (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-600 dark:text-blue-400">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" /> live
                  </span>
                ) : (
                  <span className="text-xs text-muted-foreground">{runEvents.length} events</span>
                )}
              </div>
              <div className="max-h-[420px] flex-1 overflow-auto p-2 font-mono text-xs">
                {runEvents.length === 0 ? (
                  <p className="px-2 py-6 text-center text-muted-foreground">No events for this run.</p>
                ) : (
                  runEvents.map((e) => <RunEventItem key={e.id} event={e} />)
                )}
              </div>
            </Card>
          </div>

          {/* Artifacts for this run */}
          <Card>
            <div className="border-b border-border px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><FileBox className="h-4 w-4 text-teal-500" /> Artifacts produced ({runArtifacts.length})</h2>
            </div>
            {runArtifacts.length === 0 ? (
              <EmptyState icon={FileBox} title="No artifacts yet" description="This run has not produced any deliverables." className="m-4 border-0" />
            ) : (
              <div className="divide-y divide-border">
                {runArtifacts.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-2.5">
                    <FileBox className="h-4 w-4 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-sm text-foreground">{a.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.path}</p>
                    </div>
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] uppercase text-muted-foreground">{a.kind}</span>
                    <span className="hidden text-xs text-muted-foreground sm:block">{a.producedBy}</span>
                    <span className="text-xs text-muted-foreground">{formatRelative(a.createdAt)}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}
