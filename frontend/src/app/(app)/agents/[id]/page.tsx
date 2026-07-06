'use client';

import Link from 'next/link';
import { ArrowLeft, Bot, Cpu, Plug, Sparkles, PlayCircle } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { useAgent, useRuns } from '@/src/lib/queries';
import { formatRelative, formatDuration } from '@/src/lib/format';
import type { PipelineStep } from '@/src/types';

interface HistoryRow {
  id: string;
  runId: string;
  projectName: string;
  phase: string;
  status: PipelineStep['status'];
  duration: number | null;
  when: string | null;
}

function agentLastRunFromRuns(
  agentId: string,
  runs: { id: string; startedAt: string; finishedAt: string | null; steps: PipelineStep[] }[],
): string | null {
  let latest: string | null = null;
  for (const run of runs) {
    for (const step of run.steps) {
      if (step.agent !== agentId || step.status === 'queued') continue;
      const when = step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt;
      if (when && (!latest || when > latest)) latest = when;
    }
  }
  return latest;
}

export default function AgentDetailPage({ params }: { params: { id: string } }) {
  const { data: agent, isLoading } = useAgent(params.id);
  const { data: runs } = useRuns();

  if (!isLoading && !agent) {
    return (
      <Card className="border-white/[0.06] bg-card/80 p-10 text-center">
        <p className="text-sm text-muted-foreground">Agent "{params.id}" not found.</p>
        <Button asChild variant="link"><Link href="/agents">Back to registry</Link></Button>
      </Card>
    );
  }

  const history: HistoryRow[] = (runs ?? []).flatMap((run) =>
    run.steps
      .filter((s) => s.agent === params.id && s.status !== 'queued')
      .map((s) => ({
        id: s.id,
        runId: run.id,
        projectName: run.projectName,
        phase: s.phase,
        status: s.status,
        duration: s.durationSec,
        when: s.finishedAt ?? s.startedAt ?? run.finishedAt ?? run.startedAt,
      })),
  );

  const lastRunAt = agentLastRunFromRuns(params.id, runs ?? []) ?? agent?.lastRunAt ?? null;
  const hasMcpServers = (agent?.mcpServers.length ?? 0) > 0;
  const hasBuiltinTools = (agent?.mcpTools.length ?? 0) > 0;

  const columns: Column<HistoryRow>[] = [
    {
      key: 'runId',
      header: 'Run',
      render: (r) => (
        <Link href={`/runs/${r.runId}`} className="font-mono text-xs text-teal-400 hover:underline">
          {r.runId.slice(0, 8)}…
        </Link>
      ),
    },
    { key: 'projectName', header: 'Project', render: (r) => <span className="text-foreground">{r.projectName}</span> },
    { key: 'phase', header: 'Phase', render: (r) => <span className="capitalize text-muted-foreground">{r.phase}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge status={r.status} size="sm" /> },
    { key: 'duration', header: 'Duration', render: (r) => <span className="text-muted-foreground">{formatDuration(r.duration)}</span> },
    { key: 'when', header: 'Started', render: (r) => <span className="text-muted-foreground">{formatRelative(r.when)}</span> },
  ];

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 mb-1 gap-1.5 text-muted-foreground hover:text-foreground">
        <Link href="/agents"><ArrowLeft className="h-4 w-4" /> Agent Registry</Link>
      </Button>

      <PageHeader
        title={agent?.displayName ?? params.id}
        eyebrow={agent?.name}
        description={agent?.role}
        actions={
          <div className="flex items-center gap-3">
            {agent ? <StatusBadge status={agent.availability} /> : null}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span tabIndex={0}>
                    <Button disabled variant="outline" className="gap-1.5 border-white/[0.08] text-muted-foreground">
                      <PlayCircle className="h-4 w-4" /> Test agent
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  Not available yet. A future health check will ping the AgentCore runtime without running a full pipeline task.
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="border-white/[0.06] bg-card/80 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Sparkles className="h-4 w-4 text-teal-400" /> Capabilities & Skills</h3>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {agent?.skills.map((s) => <Badge key={s} variant="secondary" className="border-white/[0.06] bg-muted/60 font-normal">{s}</Badge>)}
          </div>
          <h4 className="mt-5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
            {hasBuiltinTools ? 'Built-in tools' : 'MCP tools'}
          </h4>
          <div className="mt-2 space-y-1">
            {hasBuiltinTools ? (
              agent?.mcpTools.map((t) => (
                <code key={t} className="block rounded-md border border-white/[0.04] bg-muted/40 px-2.5 py-1.5 font-mono text-xs text-foreground">{t}</code>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">Uses MCP server tools listed on the right.</p>
            )}
          </div>
        </Card>

        <Card className="border-white/[0.06] bg-card/80 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Plug className="h-4 w-4 text-teal-400" /> MCP Servers Attached</h3>
          <div className="mt-3 space-y-2">
            {hasMcpServers ? (
              agent?.mcpServers.map((s) => (
                <div key={s} className="flex items-center gap-2.5 rounded-lg border border-white/[0.06] bg-white/[0.01] px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-white/[0.03]">
                  <Plug className="h-3.5 w-3.5 text-muted-foreground" /> {s}
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">
                No external MCP servers — this agent uses built-in Strands tools only.
              </p>
            )}
          </div>
        </Card>

        <Card className="border-white/[0.06] bg-card/80 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Cpu className="h-4 w-4 text-teal-400" /> Runtime</h3>
          <dl className="mt-3 space-y-3 text-sm">
            <div className="flex items-center justify-between"><dt className="text-muted-foreground">Port</dt><dd className="font-mono text-foreground">:{agent?.port}</dd></div>
            <div className="flex items-center justify-between"><dt className="text-muted-foreground">Availability</dt><dd>{agent ? <StatusBadge status={agent.availability} size="sm" /> : null}</dd></div>
            <div className="flex items-center justify-between"><dt className="text-muted-foreground">Default phase</dt><dd className="capitalize text-foreground">{agent?.phase ?? 'orchestration'}</dd></div>
            <div className="flex items-center justify-between"><dt className="text-muted-foreground">Last run</dt><dd className="text-foreground">{formatRelative(lastRunAt)}</dd></div>
          </dl>
        </Card>
      </div>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <Bot className="h-4 w-4 text-teal-400" />
          <h2 className="text-sm font-semibold text-foreground">Execution History</h2>
          <span className="rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">{history.length}</span>
        </div>
        <DataTable columns={columns} rows={history} getRowId={(r) => r.id} empty="No execution history for this agent yet." />
      </div>
    </>
  );
}
