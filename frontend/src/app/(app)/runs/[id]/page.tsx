'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  Workflow,
  PlayCircle,
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
  AlertTriangle,
  XCircle,
  ScrollText,
  ExternalLink,
  GitBranch,
  Ban,
} from 'lucide-react';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { OpenLiveAppLink } from '@/src/components/common/OpenLiveAppLink';
import { EmptyState } from '@/src/components/common/EmptyState';
import { LogTable } from '@/src/components/logs/LogTable';
import { useRouter } from 'next/navigation';
import {
  queryKeys,
  useRun,
  useRunEvents,
  useRunHandoffs,
  useRunLogs,
  useArtifacts,
  useCheckpoints,
} from '@/src/lib/queries';
import { api } from '@/src/lib/api';
import { formatRelative, formatDuration } from '@/src/lib/format';
import { LiveRunMonitoringLine } from '@/src/components/common/LiveElapsed';
import { TIMELINE_PHASES, phaseDisplayLabel, stepStatusHint } from '@/src/lib/pipeline-phases';
import { PipelineHandoffsCard } from '@/src/features/runs/PipelineHandoffsCard';
import { useUiStore } from '@/src/store/ui-store';
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
  queued: 'text-slate-500',
  running: 'text-blue-400',
  completed: 'text-emerald-400',
  failed: 'text-red-400',
  waiting_for_human: 'text-amber-400',
  skipped: 'text-slate-500',
};

const STEP_BG: Record<StepStatus, string> = {
  queued: 'border-white/[0.06] bg-transparent',
  running: 'border-blue-500/30 bg-blue-500/[0.04]',
  completed: 'border-emerald-500/20 bg-emerald-500/[0.03]',
  failed: 'border-red-500/20 bg-red-500/[0.03]',
  waiting_for_human: 'border-amber-500/30 bg-amber-500/[0.04]',
  skipped: 'border-white/[0.04] bg-transparent',
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
    <div className="border-b border-white/[0.04] px-2.5 py-2.5 last:border-0 transition-colors hover:bg-white/[0.01]">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-3.5 w-3.5 shrink-0', color)} />
        <span className="truncate text-foreground">{title}</span>
        <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{formatRelative(ts)}</span>
      </div>
      <p className="mt-1 pl-5 text-[12px] text-muted-foreground">{detail}</p>
    </div>
  );
}

function RunEventItem({ event }: { event: RunEvent }) {
  switch (event.kind) {
    case 'log':
      return (
        <div className="border-b border-white/[0.04] px-2.5 py-2.5 last:border-0 transition-colors hover:bg-white/[0.01]">
          <div className="flex items-center gap-2">
            <StatusBadge status={event.level} size="sm" />
            <span className="truncate text-teal-400">{event.agent}</span>
            <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{formatRelative(event.ts)}</span>
          </div>
          <p className="mt-1 pl-1 text-foreground">{event.message}</p>
        </div>
      );
    case 'phase.started':
      return <EventRow icon={PlayCircle} color="text-blue-400" ts={event.ts} title={<>Phase <span className="capitalize">{event.phase}</span> started</>} detail={event.agent} />;
    case 'phase.completed':
      return <EventRow icon={CheckCircle2} color="text-emerald-400" ts={event.ts} title={<>Phase <span className="capitalize">{event.phase}</span> completed</>} detail={`${event.agent} \u00b7 ${formatDuration(event.durationSec)}`} />;
    case 'step.failed':
      return <EventRow icon={XCircle} color="text-red-400" ts={event.ts} title={<>Step failed at <span className="capitalize">{event.phase}</span></>} detail={event.error} />;
    case 'hitl.requested':
      return <EventRow icon={UserCheck} color="text-amber-400" ts={event.ts} title="HITL requested" detail={event.title} />;
    case 'artifact.created':
      return <EventRow icon={FileBox} color="text-teal-400" ts={event.ts} title={<>Artifact <span className="font-medium">{event.artifactName}</span></>} detail={`${event.artifactKind} \u00b7 ${event.agent}`} />;
    case 'agent.message':
      return <EventRow icon={Send} color="text-blue-400" ts={event.ts} title={<><span className="font-mono">{event.messageType}</span> \u00b7 {event.from} \u2192 {event.to}</>} detail={event.summary} />;
    default:
      return null;
  }
}

export default function RunDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data: run, isLoading } = useRun(params.id);
  const isLive = run?.status === 'running' || run?.status === 'paused';
  // Phase A: keep polling handoffs while deploy is pending/running so the
  // live URL and "App is live" banner appear without a manual refresh.
  const deployActive =
    run?.deployStatus === 'pending' || run?.deployStatus === 'running';
  const { data: events } = useRunEvents(params.id, isLive);
  const { data: runLogs, isLoading: runLogsLoading } = useRunLogs(params.id, isLive);
  const { data: handoffs } = useRunHandoffs(params.id, isLive || deployActive);
  const { data: artifacts } = useArtifacts();
  const { data: checkpoints } = useCheckpoints();
  const setArtifactsProjectId = useUiStore((s) => s.setArtifactsProjectId);

  const [hitlOverride, setHitlOverride] = React.useState<Record<string, 'approved' | 'rejected'>>({});
  const [cancelling, setCancelling] = React.useState(false);

  const handleCancel = async () => {
    if (cancelling) return;
    setCancelling(true);
    try {
      const result = await api.cancelRun(params.id);
      toast.success('Run cancelled', { description: result.message });
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs });
      await queryClient.invalidateQueries({ queryKey: queryKeys.run(params.id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    } catch (err) {
      toast.error('Cancel failed', {
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setCancelling(false);
    }
  };

  if (!isLoading && !run) {
    return (
      <Card className="border-white/[0.06] bg-card/80 p-10 text-center">
        <p className="text-sm text-muted-foreground">Run &ldquo;{params.id}&rdquo; not found.</p>
        <Button asChild variant="link"><Link href="/runs">Back to runs</Link></Button>
      </Card>
    );
  }

  const status: RunStatus = run?.status ?? 'queued';
  const runArtifacts = (artifacts ?? []).filter((a) => a.runId === params.id);
  const runCheckpoints = (checkpoints ?? [])
    .filter((c) => c.runId === params.id)
    .map((c) => ({ ...c, status: hitlOverride[c.id] ?? c.status }));
  const waitingStep = run?.steps.find((s) => s.status === 'waiting_for_human') ?? null;
  const runEvents = [...(events ?? [])].sort((a, b) => +new Date(b.ts) - +new Date(a.ts));
  const displayLive = status === 'running';
  const gitlabBranchUrl = handoffs?.gitlab?.branchUrl ?? null;
  const gitlabMrUrl = handoffs?.gitlab?.mergeRequestUrl ?? handoffs?.contextMergeRequestUrl ?? null;
  const developerStepStatus = run?.steps.find((step) => step.agent === 'developer-agent')?.status;

  const resolveHitl = (id: string, title: string, decision: 'approved' | 'rejected') => {
    setHitlOverride((o) => ({ ...o, [id]: decision }));
    toast.success(`Checkpoint ${decision}`, { description: `${title} - recorded locally (mock).` });
  };

  const controls = (
    <div className="flex items-center gap-2">
      {(status === 'running' || status === 'paused') ? (
        <Button
          size="sm"
          variant="outline"
          className="gap-1.5 border-red-500/30 text-red-300 hover:bg-red-500/10 hover:text-red-200"
          onClick={handleCancel}
          disabled={cancelling}
        >
          {cancelling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Ban className="h-3.5 w-3.5" />}
          Cancel
        </Button>
      ) : null}
      <StatusBadge status={status} />
    </div>
  );

  const runDescription =
    run && status !== 'running' && status !== 'paused'
      ? `Started ${formatRelative(run.startedAt)}${
          run.elapsedSec != null ? ` · took ${formatDuration(run.elapsedSec)}` : ''
        }${run.finishedAt ? ` · finished ${formatRelative(run.finishedAt)}` : ''}`
      : undefined;

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground hover:text-foreground">
        <Link href="/runs"><ArrowLeft className="h-4 w-4" /> Pipeline Runs</Link>
      </Button>

      <PageHeader
        eyebrow={run ? `${run.id} \u00b7 ${run.pipeline}` : params.id}
        title={run?.projectName ?? params.id}
        description={
          run && (status === 'running' || status === 'paused') ? (
            <LiveRunMonitoringLine startedAt={run.startedAt} live />
          ) : (
            runDescription
          )
        }
        actions={isLoading ? null : controls}
      />

      {isLoading || !run ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Skeleton className="h-96 w-full rounded-xl lg:col-span-2" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      ) : (
        <>
          {/* Active agent banner */}
          {status === 'running' && run.currentAgent ? (
            <Card className="flex items-center gap-3 border-blue-500/30 bg-blue-500/[0.05] p-4">
              <span className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/15 text-blue-400">
                <Bot className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  <span className="font-mono">{run.currentAgent}</span> is executing the{' '}
                  <span>{phaseDisplayLabel(run.currentPhase)}</span> phase
                </p>
                <p className="text-[11px] text-muted-foreground">Live status from the platform - the control plane does not run the agent.</p>
              </div>
              <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
            </Card>
          ) : null}

          {status === 'failed' ? (
            <Card className="flex items-start gap-3 border-red-500/30 bg-red-500/[0.05] p-4">
              <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-500/15 text-red-400">
                <AlertTriangle className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">Pipeline failed</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  {run.error ?? 'See the phase timeline and event stream below for details.'}
                </p>
              </div>
            </Card>
          ) : null}

          {status === 'cancelled' ? (
            <Card className="flex items-start gap-3 border-amber-500/30 bg-amber-500/[0.05] p-4">
              <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400">
                <Ban className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">Pipeline cancelled</p>
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  {run.error ?? 'This run was cancelled. You can start a new pipeline when ready.'}
                </p>
              </div>
            </Card>
          ) : null}

          {status === 'completed' ? (
            <Card className={`flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between ${
              deployActive
                ? 'border-blue-500/30 bg-blue-500/[0.05]'
                : 'border-emerald-500/30 bg-emerald-500/[0.05]'
            }`}>
              <div className="flex items-start gap-3">
                <span className={`relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                  deployActive
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'bg-emerald-500/15 text-emerald-400'
                }`}>
                  <CheckCircle2 className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">
                    {handoffs?.devops?.appUrl
                      ? 'App is live'
                      : deployActive
                        ? 'Pipeline complete — deploying'
                        : 'Pipeline complete'}
                  </p>
                  <p className="mt-0.5 text-[12px] text-muted-foreground">
                    {handoffs?.devops?.appUrl
                      ? 'DevOps finished deploying. Open the live app or review the GitLab branch.'
                      : deployActive
                        ? 'All agents finished. GitLab CI is building and deploying your app — the live URL will appear here automatically.'
                        : handoffs?.gitlab?.status === 'published'
                          ? `${handoffs.gitlab.pathsPublishedCount} paths published to GitLab.`
                          : 'All SDLC phases finished. Review artifacts and handoffs below.'}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                {handoffs?.devops?.appUrl ? (
                  <OpenLiveAppLink href={handoffs.devops.appUrl} variant="button" className="text-xs" />
                ) : null}
                {gitlabBranchUrl ? (
                  <a
                    href={gitlabBranchUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-500/15"
                  >
                    <GitBranch className="h-3.5 w-3.5" />
                    View branch on GitLab
                    <ExternalLink className="h-3 w-3 opacity-70" />
                  </a>
                ) : null}
                {gitlabMrUrl ? (
                  <a
                    href={gitlabMrUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] px-3 py-1.5 text-xs font-medium text-teal-400 hover:bg-white/[0.03]"
                  >
                    Open merge request
                    <ExternalLink className="h-3 w-3 opacity-70" />
                  </a>
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 border-white/[0.08]"
                  onClick={() => {
                    if (run?.projectId) setArtifactsProjectId(run.projectId);
                    router.push('/artifacts');
                  }}
                >
                  Browse artifacts
                </Button>
              </div>
            </Card>
          ) : null}

          {/* Inline HITL when waiting for a human */}
          {waitingStep ? (
            (() => {
              const cp = (checkpoints ?? []).find((c) => c.runId === params.id && c.status === 'pending');
              return (
                <Card className="border-amber-500/30 bg-amber-500/[0.04] p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-start gap-3">
                      <UserCheck className="mt-0.5 h-5 w-5 text-amber-400" />
                      <div>
                        <p className="text-sm font-semibold text-foreground">{cp?.title ?? `Human approval required at ${waitingStep.phase}`}</p>
                        <p className="text-xs text-muted-foreground">{cp?.description ?? `The ${waitingStep.agent} paused this run for human review.`}</p>
                      </div>
                    </div>
                    {cp ? (
                      <div className="flex shrink-0 gap-2">
                        <Button size="sm" variant="outline" className="gap-1.5 border-white/[0.08]" onClick={() => resolveHitl(cp.id, cp.title, 'rejected')}><X className="h-4 w-4" /> Reject</Button>
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
            <Card className="border-white/[0.06] bg-card/80 lg:col-span-2">
              <div className="border-b border-white/[0.06] px-4 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Workflow className="h-4 w-4 text-teal-400" /> SDLC Phase Timeline</h2>
              </div>
              <ol className="p-4">
                {run.steps
                  .filter((step) => TIMELINE_PHASES.includes(step.phase))
                  .map((step: PipelineStep, i: number, arr) => {
                  const Icon = STEP_ICON[step.status];
                  const last = i === arr.length - 1;
                  const active = step.status === 'running' || step.status === 'waiting_for_human';
                  return (
                    <li key={step.id} className="relative flex gap-4 pb-6 last:pb-0">
                      {!last ? <span className="absolute left-[15px] top-8 h-[calc(100%-1rem)] w-px bg-white/[0.06]" /> : null}
                      <span className={cn('relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border bg-card', STEP_ICON_COLOR[step.status],
                        step.status === 'completed' ? 'border-emerald-500/30' :
                        step.status === 'running' ? 'border-blue-500/30' :
                        step.status === 'waiting_for_human' ? 'border-amber-500/30' :
                        step.status === 'failed' ? 'border-red-500/30' :
                        'border-white/[0.08]'
                      )}>
                        <Icon className={cn('h-4 w-4', step.status === 'running' && 'animate-spin')} />
                      </span>
                      <div className={cn('min-w-0 flex-1 rounded-lg border p-3 transition-all', STEP_BG[step.status])}>
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-foreground">{phaseDisplayLabel(step.phase)}</p>
                          <StatusBadge status={step.status} size="sm" />
                        </div>
                        <p className="font-mono text-xs text-muted-foreground">{step.agent}</p>
                        <div className="mt-1 flex flex-col gap-1 text-xs text-muted-foreground">
                          <div className="flex items-center gap-3">
                            <span>{stepStatusHint(step)}</span>
                            {step.durationSec != null ? <span>· {formatDuration(step.durationSec)}</span> : null}
                          </div>
                          {step.status === 'failed' && step.error ? (
                            <p className="text-[11px] leading-relaxed text-red-400/90">{step.error}</p>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </Card>

            {/* Per-run event stream (SSE-ready) */}
            <Card className="flex flex-col border-white/[0.06] bg-card/80">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Radio className="h-4 w-4 text-teal-400" /> Event Stream</h2>
                {displayLive ? (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-400">
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

          {handoffs ? (
            <PipelineHandoffsCard handoffs={handoffs} developerStepStatus={developerStepStatus} />
          ) : null}

          <Card className="border-white/[0.06] bg-card/80">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <ScrollText className="h-4 w-4 text-teal-400" /> Run logs
                {!runLogsLoading && runLogs?.length ? (
                  <span className="font-normal text-muted-foreground">({runLogs.length})</span>
                ) : null}
              </h2>
              <Button asChild variant="outline" size="sm" className="h-8 border-white/[0.08]">
                <Link href={`/logs?runId=${params.id}`}>Open in Logs</Link>
              </Button>
            </div>
            {runLogsLoading ? (
              <Skeleton className="m-4 h-48 w-full rounded-lg" />
            ) : !runLogs?.length ? (
              <EmptyState
                icon={ScrollText}
                title="No log lines yet"
                description="CloudWatch agent stdout for this run window."
                className="m-4 border-0"
              />
            ) : (
              <div className="max-h-[480px] overflow-auto p-2">
                <LogTable rows={runLogs.slice(0, 80)} showRunColumn={false} live={isLive} />
                {runLogs.length > 80 ? (
                  <p className="px-3 py-2 text-center text-xs text-muted-foreground">
                    Showing 80 of {runLogs.length}.{' '}
                    <Link href={`/logs?runId=${params.id}`} className="text-teal-400 hover:underline">
                      View all in Logs
                    </Link>
                  </p>
                ) : null}
              </div>
            )}
          </Card>

          {/* Artifacts for this run */}
          <Card className="border-white/[0.06] bg-card/80">
            <div className="border-b border-white/[0.06] px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><FileBox className="h-4 w-4 text-teal-400" /> Artifacts Produced ({runArtifacts.length})</h2>
            </div>
            {runArtifacts.length === 0 ? (
              <EmptyState icon={FileBox} title="No artifacts yet" description="This run has not produced any deliverables." className="m-4 border-0" />
            ) : (
              <div className="divide-y divide-white/[0.04]">
                {runArtifacts.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.02]">
                    <FileBox className="h-4 w-4 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-sm text-foreground">{a.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.path}</p>
                    </div>
                    <span className="rounded-md bg-muted/50 px-1.5 py-0.5 text-[11px] uppercase text-muted-foreground">{a.kind}</span>
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
