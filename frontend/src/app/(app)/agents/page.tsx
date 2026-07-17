'use client';

import * as React from 'react';
import { LayoutGrid, Table2, Bot, Loader2, Activity, CircleOff, HelpCircle, PlayCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { AgentCard } from '@/src/components/common/AgentCard';
import { DataTable, type Column } from '@/src/components/common/DataTable';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { useAgents, useRuns } from '@/src/lib/queries';
import { api } from '@/src/lib/api';
import { summarizeAgentHealthCheck } from '@/src/lib/agent-health-check';
import { computeAllAgentOpsMetrics } from '@/src/lib/agent-metrics';
import { formatRelative, formatDuration } from '@/src/lib/format';
import { useRouter } from 'next/navigation';
import type { Agent } from '@/src/types';
import { cn } from '@/lib/utils';

export default function AgentsPage() {
  const { data: rawAgents, isLoading } = useAgents();
  const { data: runs } = useRuns();
  const [view, setView] = React.useState<'cards' | 'table'>('cards');
  const [testingFleet, setTestingFleet] = React.useState(false);
  const [lastFleetCheckAt, setLastFleetCheckAt] = React.useState<string | null>(null);
  const [fleetCheckSummary, setFleetCheckSummary] = React.useState<string | null>(null);
  const router = useRouter();

  // Orchestrator is a system component - show only the specialist agents
  // Exclude web crawler per user request
  const agents = React.useMemo(
    () => (rawAgents ?? []).filter((a) => a.id !== 'orchestrator-agent' && a.id !== 'web-crawler-agent'),
    [rawAgents],
  );

  const metricsByAgent = React.useMemo(
    () => computeAllAgentOpsMetrics(agents.map((a) => a.id), runs),
    [agents, runs],
  );

  const fleet = React.useMemo(() => {
    let online = 0;
    let offline = 0;
    let unknown = 0;
    for (const a of agents) {
      if (a.availability === 'online') online += 1;
      else if (a.availability === 'offline') offline += 1;
      else unknown += 1;
    }
    return { online, offline, unknown, total: agents.length };
  }, [agents]);

  const handleTestFleet = async () => {
    const testable = agents.filter((a) => a.availability === 'online');
    if (testable.length === 0) {
      toast.error('No online agents to test', {
        description: 'Fleet health checks only invoke agents marked online.',
      });
      return;
    }

    setTestingFleet(true);
    let ok = 0;
    let failed = 0;
    try {
      for (const agent of testable) {
        try {
          const result = await api.testAgent(agent.id);
          const summary = summarizeAgentHealthCheck(agent.displayName, result);
          if (summary.ok) {
            ok += 1;
            toast.success(summary.title, { description: summary.description });
          } else {
            failed += 1;
            toast.error(summary.title, { description: summary.description });
          }
        } catch (err) {
          failed += 1;
          toast.error(`${agent.displayName} health check failed`, {
            description: err instanceof Error ? err.message : String(err),
          });
        }
      }
      const at = new Date().toISOString();
      setLastFleetCheckAt(at);
      setFleetCheckSummary(`${ok} passed · ${failed} failed · ${testable.length} tested`);
      if (failed === 0) {
        toast.success('Fleet health check complete', {
          description: `All ${ok} online agent(s) responded.`,
        });
      } else {
        toast.warning('Fleet health check complete', {
          description: `${ok} passed, ${failed} failed.`,
        });
      }
    } finally {
      setTestingFleet(false);
    }
  };

  const columns: Column<Agent>[] = [
    {
      key: 'name',
      header: 'Agent',
      render: (a) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400 ring-1 ring-inset ring-teal-500/20">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <p className="font-medium text-foreground">{a.displayName}</p>
            <p className="font-mono text-xs text-muted-foreground">{a.name}</p>
          </div>
        </div>
      ),
    },
    { key: 'role', header: 'Role', className: 'max-w-md', render: (a) => <span className="line-clamp-2 text-muted-foreground">{a.role}</span> },
    {
      key: 'success',
      header: 'Success',
      render: (a) => {
        const m = metricsByAgent[a.id];
        if (m?.successRatePct == null) return <span className="text-muted-foreground">-</span>;
        return (
          <span className="tabular-nums text-foreground">
            {m.successRatePct}% <span className="text-muted-foreground">({m.sampleSize})</span>
          </span>
        );
      },
    },
    {
      key: 'avg',
      header: 'Avg duration',
      render: (a) => {
        const m = metricsByAgent[a.id];
        return (
          <span className="tabular-nums text-muted-foreground">
            {m?.avgDurationSec != null ? formatDuration(Math.round(m.avgDurationSec)) : '-'}
          </span>
        );
      },
    },
    {
      key: 'tools',
      header: 'Tools',
      render: (a) => {
        const items = a.mcpServers.length > 0 ? a.mcpServers : a.mcpTools;
        return (
          <div className="flex flex-wrap gap-1">
            {items.slice(0, 2).map((t) => (
              <span key={t} className="rounded-md bg-muted/60 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">{t}</span>
            ))}
            {items.length > 2 ? <span className="text-[11px] text-muted-foreground">+{items.length - 2}</span> : null}
          </div>
        );
      },
    },
    { key: 'availability', header: 'Status', render: (a) => <StatusBadge status={a.availability} size="sm" /> },
    {
      key: 'lastRunAt',
      header: 'Last active',
      render: (a) => (
        <span className="text-muted-foreground">
          {formatRelative(metricsByAgent[a.id]?.lastActiveAt ?? a.lastRunAt)}
        </span>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Agent Registry"
        description="Specialist agents that execute the SDLC pipeline. Each runs as a standalone service with MCP tool access."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="h-8 gap-1.5"
              onClick={handleTestFleet}
              disabled={testingFleet || isLoading || agents.length === 0}
            >
              {testingFleet ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlayCircle className="h-3.5 w-3.5" />}
              Test fleet
            </Button>
            <div className="flex items-center rounded-lg border border-white/[0.08] bg-muted/40 p-0.5">
              <Button variant={view === 'cards' ? 'secondary' : 'ghost'} size="sm" className="h-7 px-2" onClick={() => setView('cards')}>
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button variant={view === 'table' ? 'secondary' : 'ghost'} size="sm" className="h-7 px-2" onClick={() => setView('table')}>
                <Table2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
        }
      />

      {/* Fleet health strip */}
      <div className="mb-6 flex flex-col gap-3 rounded-xl border border-white/[0.06] bg-card/60 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          <span className="font-medium text-foreground">Fleet health</span>
          <span className={cn('inline-flex items-center gap-1.5', fleet.online > 0 ? 'text-emerald-400' : 'text-muted-foreground')}>
            <Activity className="h-3.5 w-3.5" />
            <span className="tabular-nums font-medium">{fleet.online}</span> online
          </span>
          <span className={cn('inline-flex items-center gap-1.5', fleet.offline > 0 ? 'text-red-400' : 'text-muted-foreground')}>
            <CircleOff className="h-3.5 w-3.5" />
            <span className="tabular-nums font-medium">{fleet.offline}</span> offline
          </span>
          <span className={cn('inline-flex items-center gap-1.5', fleet.unknown > 0 ? 'text-amber-400' : 'text-muted-foreground')}>
            <HelpCircle className="h-3.5 w-3.5" />
            <span className="tabular-nums font-medium">{fleet.unknown}</span> unknown
          </span>
          <span className="text-muted-foreground">
            <span className="tabular-nums">{fleet.total}</span> agents
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {lastFleetCheckAt
            ? <>Last check {formatRelative(lastFleetCheckAt)}{fleetCheckSummary ? ` · ${fleetCheckSummary}` : ''}</>
            : 'No fleet check yet - use Test fleet to ping online agents.'}
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-48 w-full rounded-xl" />)}
        </div>
      ) : view === 'cards' ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => (
            <AgentCard key={a.id} agent={a} metrics={metricsByAgent[a.id]} />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} rows={agents} getRowId={(a) => a.id} onRowClick={(a) => router.push(`/agents/${a.id}`)} />
      )}
    </>
  );
}
