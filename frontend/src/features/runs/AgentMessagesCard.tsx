'use client';

import { ArrowRight, MessagesSquare, Bot, CheckCircle2, XCircle, Loader2, UserCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useRunAgentMessages } from '@/src/lib/queries';
import { formatRelative } from '@/src/lib/format';
import type { AgentMessageType } from '@/src/types';

const AGENT_LABEL: Record<string, string> = {
  'orchestrator-agent': 'Orchestrator',
  'product-agent': 'Product',
  'architect-agent': 'Architect',
  'database-agent': 'Database',
  'developer-agent': 'Developer',
  'gitlab-agent': 'GitLab',
  'qa-agent': 'QA',
  'security-agent': 'Security',
};

const TYPE_META: Record<AgentMessageType, { label: string; icon: typeof Bot; color: string }> = {
  'task.assign': { label: 'assign', icon: ArrowRight, color: 'text-blue-400' },
  'task.result': { label: 'result', icon: CheckCircle2, color: 'text-emerald-400' },
  'task.error': { label: 'error', icon: XCircle, color: 'text-red-400' },
  'status.update': { label: 'update', icon: Loader2, color: 'text-amber-400' },
  'hitl.request': { label: 'hitl', icon: UserCheck, color: 'text-amber-400' },
  'hitl.resolved': { label: 'hitl resolved', icon: UserCheck, color: 'text-emerald-400' },
};

function agentName(id: string): string {
  return AGENT_LABEL[id] ?? id;
}

export function AgentMessagesCard({ runId, live = false }: { runId: string; live?: boolean }) {
  const { data: messages, isLoading } = useRunAgentMessages(runId, live);

  return (
    <Card className="border-white/[0.06] bg-card/80" data-testid="agent-messages-card">
      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <MessagesSquare className="h-4 w-4 text-teal-400" /> Orchestrator messages
        </h2>
        {!isLoading && messages ? (
          <span className="text-xs text-muted-foreground">{messages.length} handoffs</span>
        ) : null}
      </div>

      {isLoading ? (
        <Skeleton className="m-4 h-40 rounded-lg" />
      ) : !messages?.length ? (
        <p className="px-4 py-10 text-center text-sm text-muted-foreground" data-testid="agent-messages-empty">
          No A2A handoff messages for this run yet.
        </p>
      ) : (
        <ol className="p-4">
          {messages.map((m, i, arr) => {
            const meta = TYPE_META[m.type];
            const Icon = meta.icon;
            const last = i === arr.length - 1;
            return (
              <li key={m.id} className="relative flex gap-3 pb-5 last:pb-0" data-testid="agent-message-row">
                {!last ? <span className="absolute left-[13px] top-7 h-[calc(100%-1rem)] w-px bg-white/[0.06]" /> : null}
                <span
                  className={cn(
                    'relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-card',
                    meta.color,
                  )}
                >
                  <Icon className={cn('h-3.5 w-3.5', m.type === 'status.update' && 'animate-spin')} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                    <span className="font-medium text-teal-400">{agentName(m.from)}</span>
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                    <span className="font-medium text-foreground">{agentName(m.to)}</span>
                    <span className={cn('ml-1 rounded-md bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] uppercase', meta.color)}>
                      {meta.label}
                    </span>
                    <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{formatRelative(m.ts)}</span>
                  </div>
                  <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">{m.summary}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Card>
  );
}
