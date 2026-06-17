'use client';

import Link from 'next/link';
import { Network, ArrowRight, Bot } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { MessageTypeBadge } from '@/src/components/common/MessageTypeBadge';
import { OrchestratorFlow } from '@/src/components/flow/OrchestratorFlow';
import { useAgents, useAgentMessages } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';

export default function OrchestratorPage() {
  const { data: agents, isLoading } = useAgents();
  const { data: messages } = useAgentMessages();

  const orchestrator = agents?.find((a) => a.id === 'orchestrator-agent');
  const specialists = (agents ?? []).filter((a) => a.id !== 'orchestrator-agent');
  const timeline = [...(messages ?? [])].sort((a, b) => +new Date(b.ts) - +new Date(a.ts));
  const activeDelegations = new Set(
    (messages ?? []).filter((m) => m.type === 'task.assign').map((m) => m.correlationId),
  ).size;

  return (
    <>
      <PageHeader
        eyebrow="Design"
        title="Orchestrator"
        description="The orchestrator-agent coordinates specialists across the SDLC pipeline and routes human-in-the-loop checkpoints."
        actions={
          <Button asChild variant="outline" size="sm" className="gap-1.5">
            <Link href="/orchestrator/messages">Message log <ArrowRight className="h-4 w-4" /></Link>
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card className="p-4"><p className="text-xs text-muted-foreground">Specialists</p><p className="mt-1 text-2xl font-semibold text-foreground">{specialists.length}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">Online</p><p className="mt-1 text-2xl font-semibold text-emerald-600 dark:text-emerald-400">{specialists.filter((a) => a.availability === 'online').length}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">Delegation threads</p><p className="mt-1 text-2xl font-semibold text-foreground">{activeDelegations}</p></Card>
        <Card className="p-4"><p className="text-xs text-muted-foreground">Bus messages</p><p className="mt-1 text-2xl font-semibold text-foreground">{messages?.length ?? 0}</p></Card>
      </div>

      {isLoading ? (
        <Skeleton className="h-[520px] w-full rounded-lg" />
      ) : (
        <OrchestratorFlow orchestrator={orchestrator} specialists={specialists} />
      )}

      <Card className="flex flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground"><Network className="h-4 w-4 text-teal-500" /> Delegation timeline</h2>
          <Button asChild variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground">
            <Link href="/orchestrator/messages">View all <ArrowRight className="h-3 w-3" /></Link>
          </Button>
        </div>
        <ol className="relative space-y-4 p-4 pl-8">
          <span className="absolute left-[18px] top-4 h-[calc(100%-2rem)] w-px bg-border" />
          {timeline.map((m) => (
            <li key={m.id} className="relative">
              <span className="absolute -left-[22px] top-1 flex h-3 w-3 items-center justify-center rounded-full border-2 border-background bg-teal-500" />
              <div className="flex flex-wrap items-center gap-2">
                <MessageTypeBadge type={m.type} />
                <span className="text-sm text-foreground">
                  <span className="font-mono text-xs">{m.from}</span>
                  <ArrowRight className="mx-1 inline h-3 w-3 text-muted-foreground" />
                  <span className="font-mono text-xs">{m.to}</span>
                </span>
                <span className="ml-auto text-xs text-muted-foreground">{formatRelative(m.ts)}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{m.summary}</p>
              <Link href={`/orchestrator/messages?correlationId=${m.correlationId}`} className="font-mono text-[11px] text-teal-600 hover:underline dark:text-teal-400">{m.correlationId}</Link>
            </li>
          ))}
        </ol>
      </Card>

      <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><Bot className="h-3.5 w-3.5" /> The control plane visualizes delegation only — it never executes agents.</p>
    </>
  );
}
