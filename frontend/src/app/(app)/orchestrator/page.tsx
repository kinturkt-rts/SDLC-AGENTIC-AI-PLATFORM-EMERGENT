'use client';

import Link from 'next/link';
import { Network, ArrowRight } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { PipelineFlow } from '@/src/components/flow/PipelineFlow';
import { useAgents, useAgentMessages, useRuns } from '@/src/lib/queries';
import { ORCHESTRATED_PIPELINE_AGENTS, COMPLETION_PHASES, PHASE_AGENT } from '@/src/lib/pipeline-phases';
import type { PipelineDefinition } from '@/src/types';

const ORCHESTRATED_PIPELINE_DEF: PipelineDefinition = {
  id: 'orchestrated-pipeline',
  name: 'Orchestrated Pipeline',
  description: 'Runs in this order for every pipeline request.',
  phases: COMPLETION_PHASES.map((phase) => ({ phase, agent: PHASE_AGENT[phase], hitl: false })),
};

export default function OrchestratorPage() {
  const { data: agents, isLoading } = useAgents();
  const { data: runs } = useRuns();
  const hasLiveRuns = (runs ?? []).some((r) => r.status === 'running' || r.status === 'paused');
  const { data: messages } = useAgentMessages(undefined, hasLiveRuns);

  const specialists = (agents ?? []).filter((a) => a.id !== 'orchestrator-agent');
  const individualCount = specialists.length - ORCHESTRATED_PIPELINE_AGENTS.length;

  const activeDelegations = new Set(
    (messages ?? [])
      .filter((m) => m.type === 'task.assign' || m.type === 'status.update')
      .filter((m) => (runs ?? []).some((r) => r.id === m.runId && (r.status === 'running' || r.status === 'paused')))
      .map((m) => m.correlationId),
  ).size;

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Orchestrator"
        description="The orchestrator runs product, architect, database, developer, and gitlab agents in a fixed sequence for every pipeline request. Every other agent runs on its own, outside that sequence - optionally, asynchronously, or not wired in yet."
        actions={
          <Button asChild variant="outline" size="sm" className="gap-1.5 border-white/[0.08]">
            <Link href="/orchestrator/messages">Message log <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="border-white/[0.06] bg-card/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Specialists</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground">{specialists.length}</p>
        </Card>
        <Card className="border-white/[0.06] bg-card/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Online</p>
          <p className="mt-1.5 text-2xl font-bold text-emerald-400">{specialists.filter((a) => a.availability === 'online').length}</p>
        </Card>
        <Card className="border-white/[0.06] bg-card/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Active handoffs</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground">{activeDelegations}</p>
        </Card>
        <Card className="border-white/[0.06] bg-card/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Messages</p>
          <p className="mt-1.5 text-2xl font-bold text-foreground">{messages?.length ?? 0}</p>
        </Card>
      </div>

      {isLoading ? (
        <Skeleton className="h-[280px] w-full rounded-xl" />
      ) : (
        <Card className="border-white/[0.06] bg-card/80 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Network className="h-4 w-4 text-teal-400" />
            <h2 className="text-sm font-semibold text-foreground">Orchestrated Pipeline</h2>
            <span className="text-xs text-muted-foreground">drag to pan, scroll to zoom</span>
          </div>
          <PipelineFlow pipeline={ORCHESTRATED_PIPELINE_DEF} />
          {individualCount > 0 ? (
            <p className="mt-3 border-t border-white/[0.06] pt-3 text-xs text-muted-foreground">
              {individualCount} other agent{individualCount === 1 ? '' : 's'} (QA, Security, DevOps, Web Crawler) run
              independently, outside this sequence - see the full roster on the{' '}
              <Link href="/agents" className="text-teal-500 hover:underline">Agents</Link> page.
            </p>
          ) : null}
        </Card>
      )}
    </>
  );
}
