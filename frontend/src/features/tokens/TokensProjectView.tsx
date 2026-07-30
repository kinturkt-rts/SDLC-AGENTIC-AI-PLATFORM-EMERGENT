'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  Bot,
  Coins,
  Clock,
  Layers,
  Wrench,
  TrendingUp,
  ArrowRight,
  ChevronLeft,
  Rocket,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { EmptyState } from '@/src/components/common/EmptyState';
import { PipelineModelsBanner } from '@/src/features/tokens/PipelineModelsBanner';
import { TokensOverview } from '@/src/features/tokens/TokensOverview';
import { TokenUsageChart } from '@/src/features/tokens/TokenUsageChart';
import { usePipelineTelemetry, useProjects, useRuns } from '@/src/lib/queries';
import { formatDuration, formatRelative } from '@/src/lib/format';
import {
  AGENT_TOKEN_ACCENT,
  AGENT_TOKEN_ICON,
  expectedModelForAgent,
  formatCacheHitRatio,
  formatTokenCount,
  modelDisplayLabel,
} from '@/src/lib/token-display';
import { cn } from '@/lib/utils';
import { useUiStore } from '@/src/store/ui-store';

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon: typeof Coins;
}) {
  return (
    <Card className="border-white/[0.06] bg-card/80 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
          <p className="mt-1 text-2xl font-bold tracking-tight text-foreground">{value}</p>
          {sub ? <p className="mt-1 text-[11px] text-muted-foreground">{sub}</p> : null}
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 ring-1 ring-teal-500/20">
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </Card>
  );
}

export function TokensProjectView({
  projectId,
  poll,
}: {
  projectId: string | null;
  poll?: boolean;
}) {
  const { data: projects } = useProjects();
  const { data: runs } = useRuns();
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);
  const { data, isLoading, isFetching } = usePipelineTelemetry(projectId, poll ?? false);

  const projectName = projects?.find((p) => p.id === projectId)?.name ?? data?.projectName ?? projectId;
  const agents = data?.agents ?? [];
  const reportingAgents = agents.filter((a) => a.hasTelemetry);
  const totals = data?.totals;
  const maxTokens = Math.max(...agents.map((a) => a.totalTokens), 1);

  const projectRuns = (runs ?? [])
    .filter((r) => r.projectId === projectId)
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, 8);

  const latestRun = projectRuns[0];
  const telemetryRunId = data?.runId ?? latestRun?.id ?? null;
  const runHref = telemetryRunId ? `/runs/${telemetryRunId}` : null;
  const runLabel = telemetryRunId ? `${telemetryRunId.slice(0, 8)}…` : null;

  const hasActiveRun = projectRuns.some((r) => r.status === 'running' || r.status === 'paused');

  if (!projectId) {
    return (
      <>
        <PageHeader
          eyebrow="Observe"
          title="Token usage"
          description="Bedrock token and cost estimates per project. Select a project below."
        />
        <div className="space-y-4">
          <PipelineModelsBanner />
          <div>
            <h2 className="mb-3 text-sm font-semibold text-foreground">Projects with pipeline runs</h2>
            <TokensOverview />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setTokensProjectId(null)}
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-teal-400"
      >
        <ChevronLeft className="h-4 w-4" />
        All projects
      </button>
      <PageHeader
        eyebrow="Observe"
        title="Token usage"
        description={`Bedrock token and cost estimates for ${projectName}.`}
        actions={
          poll && isFetching && reportingAgents.length > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-md bg-blue-500/10 px-2 py-1 text-[11px] font-medium text-blue-400">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" /> refreshing
            </span>
          ) : data?.updatedAt ? (
            <span className="text-xs text-muted-foreground">
              {data.runId ? (
                <>
                  Run {data.runId.slice(0, 8)}… · {data.source === 's3' ? 'S3' : 'local'} · updated{' '}
                  {formatRelative(data.updatedAt)}
                </>
              ) : (
                <>Updated {formatRelative(data.updatedAt)}</>
              )}
            </span>
          ) : data?.runId && runHref ? (
            <Link
              href={runHref}
              className="font-mono text-xs text-muted-foreground hover:text-teal-400"
            >
              Run {data.runId.slice(0, 8)}…
            </Link>
          ) : null
        }
      />

      <div className="mb-4">
        <PipelineModelsBanner />
      </div>

      {isLoading ? (
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : reportingAgents.length === 0 ? (
        <EmptyState
          icon={Coins}
          title={hasActiveRun ? 'Waiting for token usage' : 'No token usage recorded'}
          description={
            hasActiveRun ? (
              <>
                {projectName} is running now. Usage by agent and model will show up here as each step
                finishes.
              </>
            ) : telemetryRunId && runHref ? (
              <>
                {projectName} finished run{' '}
                <Link href={runHref} className="font-mono text-teal-400 hover:underline">
                  {runLabel}
                </Link>
                , but token usage was not saved for that run. Start a new run from the dashboard - usage
                will appear here as each agent completes.
              </>
            ) : (
              <>
                {projectName} has no saved token usage yet. Start a run from the dashboard and check back
                here when agents finish.
              </>
            )
          }
          action={
            <div className="flex flex-wrap items-center justify-center gap-4">
              {runHref && !hasActiveRun ? (
                <Link href={runHref} className="text-sm font-medium text-teal-400 hover:underline">
                  View run
                </Link>
              ) : null}
              <Link href="/dashboard" className="text-sm font-medium text-teal-400 hover:underline">
                {hasActiveRun ? 'Back to dashboard' : 'Start a new run'}
              </Link>
            </div>
          }
        />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatCard
              label="Billed tokens"
              value={formatTokenCount(totals?.totalTokens ?? 0)}
              sub={`${formatTokenCount(totals?.inputTokens ?? 0)} in · ${formatTokenCount(totals?.outputTokens ?? 0)} out`}
              icon={Coins}
            />
            <StatCard
              label="Est. cost"
              value={`$${(totals?.costUsd ?? 0).toFixed(2)}`}
              sub="Bedrock on-demand (incl. cache)"
              icon={TrendingUp}
            />
            <StatCard
              label="Wall time"
              value={formatDuration(Math.round(totals?.elapsedSec ?? 0))}
              sub={`${reportingAgents.length}/4 pipeline agents reported`}
              icon={Clock}
            />
            <StatCard
              label="Cache hit"
              value={`${totals?.cacheHitRatio ?? 0}%`}
              sub={`${formatTokenCount(totals?.cacheReadInputTokens ?? 0)} cache-read tokens`}
              icon={Layers}
            />
            <StatCard
              label="Deploy time"
              value={data?.deploySec != null ? formatDuration(data.deploySec) : '—'}
              sub={
                data?.deployStatus === 'live'
                  ? 'GitLab publish → live URL'
                  : data?.deployStatus === 'deploying'
                    ? 'Deploying now…'
                    : data?.deployStatus === 'failed'
                      ? 'Deploy failed'
                      : 'No deploy data yet'
              }
              icon={Rocket}
            />
          </div>

          <TokenUsageChart agents={reportingAgents} />

          <Card className="overflow-hidden border-white/[0.06] bg-card/80">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
              <div className="flex items-center gap-2">
                <Bot className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-foreground">By agent</h2>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {totals?.toolCount ?? 0} tool calls · {totals?.modelCount ?? 0} model
                {(totals?.modelCount ?? 0) === 1 ? '' : 's'}
              </span>
            </div>
            <div className="divide-y divide-white/[0.04]">
              {agents.map((entry) => {
                const Icon = AGENT_TOKEN_ICON[entry.agentId] ?? Bot;
                const accent = AGENT_TOKEN_ACCENT[entry.agentId] ?? 'bg-teal-400';
                const expected = expectedModelForAgent(entry.agentId);
                const modelLabel = entry.hasTelemetry
                  ? modelDisplayLabel(entry.modelLabel)
                  : expected.display;
                return (
                  <div
                    key={entry.agentId}
                    className={cn('px-4 py-3', !entry.hasTelemetry && 'opacity-50')}
                  >
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted/40 ring-1 ring-white/[0.06]">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <Link
                              href={`/agents/${entry.agentId}`}
                              className="text-sm font-medium text-foreground hover:text-teal-400"
                            >
                              {entry.agentName}
                            </Link>
                            <span className="rounded-md bg-muted/50 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                              {modelLabel}
                            </span>
                            {!entry.hasTelemetry ? (
                              <span className="text-[10px] text-muted-foreground">no telemetry yet</span>
                            ) : null}
                          </div>
                          {entry.hasTelemetry ? (
                            <p className="mt-0.5 text-[11px] text-muted-foreground">
                              {formatTokenCount(entry.inputTokens)} in · {formatTokenCount(entry.outputTokens)} out
                              {entry.cacheReadInputTokens > 0
                                ? ` · ${formatCacheHitRatio(entry.inputTokens, entry.cacheReadInputTokens)} cache`
                                : ''}
                              {entry.toolCount > 0 ? ` · ${entry.toolCount} tools` : ''}
                              {entry.elapsedSec > 0 ? ` · ${formatDuration(Math.round(entry.elapsedSec))}` : ''}
                            </p>
                          ) : (
                            <p className="mt-0.5 text-[11px] text-muted-foreground">
                              Expected: {expected.display}
                            </p>
                          )}
                        </div>
                      </div>
                      {entry.hasTelemetry ? (
                        <div className="flex shrink-0 items-center gap-4 text-sm sm:text-right">
                          <div>
                            <p className="font-mono font-medium text-foreground">
                              {formatTokenCount(entry.totalTokens)}
                            </p>
                            <p className="text-[11px] text-muted-foreground">billed</p>
                          </div>
                          <div>
                            <p className="font-medium text-foreground">${entry.costUsd.toFixed(2)}</p>
                            <p className="text-[11px] text-muted-foreground">est.</p>
                          </div>
                        </div>
                      ) : null}
                    </div>
                    {entry.hasTelemetry ? (
                      <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
                        <div
                          className={cn('h-full rounded-full transition-all duration-500', accent)}
                          style={{ width: `${(entry.totalTokens / maxTokens) * 100}%` }}
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="border-white/[0.06] bg-card/80 p-4 lg:col-span-2">
              <div className="flex items-center gap-2">
                <Wrench className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold text-foreground">Cost breakdown</h2>
              </div>
              <dl className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Input tokens</dt>
                  <dd className="font-mono text-foreground">{formatTokenCount(totals?.inputTokens ?? 0)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Output tokens</dt>
                  <dd className="font-mono text-foreground">{formatTokenCount(totals?.outputTokens ?? 0)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Cache read</dt>
                  <dd className="font-mono text-foreground">{formatTokenCount(totals?.cacheReadInputTokens ?? 0)}</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt className="text-muted-foreground">Cache write</dt>
                  <dd className="font-mono text-foreground">{formatTokenCount(totals?.cacheWriteInputTokens ?? 0)}</dd>
                </div>
                <div className="flex justify-between gap-2 border-t border-white/[0.06] pt-2 font-medium">
                  <dt className="text-foreground">Total estimate</dt>
                  <dd className="text-foreground">${(totals?.costUsd ?? 0).toFixed(2)}</dd>
                </div>
              </dl>
            </Card>

            <Card className="overflow-hidden border-white/[0.06] bg-card/80 lg:col-span-3">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
                <h2 className="text-sm font-semibold text-foreground">Recent pipeline runs</h2>
                <Link
                  href="/runs"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-teal-400"
                >
                  All runs <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
              {projectRuns.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No runs recorded for this project yet.
                </p>
              ) : (
                <div className="divide-y divide-white/[0.04]">
                  {projectRuns.map((run, idx) => (
                    <Link
                      key={run.id}
                      href={`/runs/${run.id}`}
                      className="flex items-center justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.02]"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-foreground">{run.id.slice(0, 8)}…</span>
                          <StatusBadge status={run.status} size="sm" />
                          {idx === 0 && hasActiveRun && (run.status === 'running' || run.status === 'paused') ? (
                            <span className="text-[10px] font-medium text-blue-400">live</span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {formatRelative(run.startedAt)} · {formatDuration(run.elapsedSec)}
                          {run.currentAgent ? ` · ${run.currentAgent.replace('-agent', '')}` : ''}
                        </p>
                      </div>
                      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/40" />
                    </Link>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
