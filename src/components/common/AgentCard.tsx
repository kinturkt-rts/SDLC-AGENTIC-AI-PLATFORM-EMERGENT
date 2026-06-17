import Link from 'next/link';
import { Bot, Cpu, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from './StatusBadge';
import { formatRelative } from '@/src/lib/format';
import type { Agent } from '@/src/types';

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link href={`/agents/${agent.id}`} className="group block">
      <Card className="h-full p-4 transition-colors hover:border-teal-400/60 hover:bg-accent/40">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-teal-500/10 text-teal-600 ring-1 ring-inset ring-teal-500/20 dark:text-teal-400">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <p className="font-semibold leading-tight text-foreground group-hover:text-teal-600 dark:group-hover:text-teal-400">
                {agent.displayName}
              </p>
              <p className="font-mono text-xs text-muted-foreground">{agent.name}</p>
            </div>
          </div>
          <StatusBadge status={agent.availability} size="sm" />
        </div>

        <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{agent.role}</p>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {agent.mcpServers.slice(0, 3).map((s) => (
            <Badge key={s} variant="secondary" className="font-normal">
              {s}
            </Badge>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5" /> :{agent.port}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" /> {formatRelative(agent.lastRunAt)}
          </span>
        </div>
      </Card>
    </Link>
  );
}
