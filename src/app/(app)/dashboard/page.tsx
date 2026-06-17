'use client';

import Link from 'next/link';
import {
  Activity,
  UserCheck,
  Bot,
  Plug,
  ArrowRight,
  FileBox,
  Timer,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import {
  useDashboardSummary,
  useRuns,
  useCheckpoints,
  useArtifacts,
  useAgents,
  useMcpServers,
} from '@/src/lib/queries';
import { formatRelative, formatDuration, titleCase } from '@/src/lib/format';

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: typeof Activity;
  label: string;
  value: React.ReactNode;
  sub?: string;
  accent?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        <div className={`flex h-8 w-8 items-center justify-center rounded-md ${accent ?? 'bg-muted text-muted-foreground'}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">{value}</p>
      {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
    </Card>
  );
}

function SectionCard({ title, href, children }: { title: string; href?: string; children: React.ReactNode }) {
  return (
    <Card className="flex flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {href ? (
          <Button asChild variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground">
            <Link href={href}>
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
        ) : null}
      </div>
      <div className="p-2">{children}</div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data: summary } = useDashboardSummary();
  const { data: runs } = useRuns();
  const { data: checkpoints } = useCheckpoints();
  const { data: artifacts } = useArtifacts();
  const { data: agents } = useAgents();
  const { data: mcp } = useMcpServers();

  const activeRuns = (runs ?? []).filter((r) => r.status === 'running' || r.status === 'paused');
  const pending = (checkpoints ?? []).filter((c) => c.status === 'pending');
  const recentArtifacts = [...(artifacts ?? [])]
    .sort((a, b) => +new Date(b.createdAt) - +new Date(a.createdAt))
    .slice(0, 10);

  return (
    <>
      <PageHeader
        eyebrow="Operate"
        title="Dashboard"
        description="Live view of pipeline runs, human approvals, and platform health across all target apps."
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {summary ? (
          <>
            <StatCard icon={Activity} label="Active runs" value={summary.activeRuns} sub="currently executing" accent="bg-blue-500/10 text-blue-600 dark:text-blue-400" />
            <StatCard icon={UserCheck} label="Pending approvals" value={summary.pendingApprovals} sub="awaiting human review" accent="bg-amber-500/10 text-amber-600 dark:text-amber-400" />
            <StatCard icon={Bot} label="Agents online" value={`${summary.agentsOnline}/${summary.agentsTotal}`} sub="specialist agents" accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" />
            <StatCard icon={Plug} label="MCP healthy" value={`${summary.mcpHealthy}/${summary.mcpTotal}`} sub="integration servers" accent="bg-teal-500/10 text-teal-600 dark:text-teal-400" />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded-lg" />)
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SectionCard title="Active pipeline runs" href="/runs">
            <div className="divide-y divide-border">
              {activeRuns.length === 0 ? (
                <p className="px-2 py-6 text-center text-sm text-muted-foreground">No active runs.</p>
              ) : (
                activeRuns.map((run) => (
                  <Link key={run.id} href={`/runs/${run.id}`} className="flex items-center gap-3 rounded-md px-2 py-3 transition-colors hover:bg-accent/40">
                    <StatusBadge status={run.status} size="sm" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">{run.projectName}</p>
                      <p className="truncate font-mono text-xs text-muted-foreground">{run.id} · {run.pipeline}</p>
                    </div>
                    <div className="hidden text-right sm:block">
                      <p className="text-xs text-muted-foreground">current</p>
                      <p className="text-sm font-medium text-foreground">{run.currentAgent ? titleCase(run.currentAgent.replace('-agent', '')) : '—'}</p>
                    </div>
                    <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Timer className="h-3.5 w-3.5" /> {formatDuration(run.elapsedSec)}
                    </div>
                  </Link>
                ))
              )}
            </div>
          </SectionCard>

          <div className="mt-4">
            <SectionCard title="Recent artifacts" href="/artifacts">
              <div className="divide-y divide-border">
                {recentArtifacts.map((a) => (
                  <div key={a.id} className="flex items-center gap-3 px-2 py-2.5">
                    <div className="flex h-7 w-7 items-center justify-center rounded bg-muted text-muted-foreground">
                      <FileBox className="h-3.5 w-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-sm text-foreground">{a.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{a.projectName} · {a.producedBy}</p>
                    </div>
                    <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium uppercase text-muted-foreground">{a.kind}</span>
                    <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">{formatRelative(a.createdAt)}</span>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </div>

        <div className="space-y-4">
          <SectionCard title="Pending HITL approvals" href="/checkpoints">
            <div className="space-y-2 p-1">
              {pending.length === 0 ? (
                <p className="px-2 py-6 text-center text-sm text-muted-foreground">Nothing waiting.</p>
              ) : (
                pending.map((c) => (
                  <div key={c.id} className="rounded-md border border-amber-200/60 bg-amber-50/50 p-3 dark:border-amber-900/50 dark:bg-amber-950/20">
                    <p className="text-sm font-medium text-foreground">{c.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{c.projectName} · {c.phase} · {formatRelative(c.requestedAt)}</p>
                  </div>
                ))
              )}
            </div>
          </SectionCard>

          <SectionCard title="MCP health" href="/mcp">
            <div className="space-y-1 p-1">
              {(mcp ?? []).map((m) => (
                <div key={m.id} className="flex items-center justify-between px-2 py-1.5">
                  <span className="text-sm text-foreground">{m.name}</span>
                  <StatusBadge status={m.status} size="sm" />
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>

      <Card>
        <div className="border-b border-border px-4 py-3">
          <h2 className="text-sm font-semibold text-foreground">Agent health</h2>
        </div>
        <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-3">
          {(agents ?? []).map((a) => (
            <Link key={a.id} href={`/agents/${a.id}`} className="flex items-center justify-between bg-card px-4 py-3 transition-colors hover:bg-accent/50">
              <div className="flex items-center gap-2.5">
                <Bot className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium text-foreground">{a.displayName}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">:{a.port}</p>
                </div>
              </div>
              <StatusBadge status={a.availability} size="sm" />
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}
