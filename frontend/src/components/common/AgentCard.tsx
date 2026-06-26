import Link from 'next/link';
import { Bot, Cpu, Clock, Zap } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from './StatusBadge';
import { formatRelative } from '@/src/lib/format';
import { cn } from '@/lib/utils';
import type { Agent } from '@/src/types';

const AGENT_ACCENTS: Record<string, { border: string; gradient: string; iconBg: string; iconColor: string }> = {
  'product-agent':   { border: 'hover:border-blue-500/30',   gradient: 'from-blue-500 to-blue-400',   iconBg: 'bg-blue-500/10',   iconColor: 'text-blue-400' },
  'architect-agent': { border: 'hover:border-violet-500/30', gradient: 'from-violet-500 to-violet-400', iconBg: 'bg-violet-500/10', iconColor: 'text-violet-400' },
  'database-agent':  { border: 'hover:border-emerald-500/30',gradient: 'from-emerald-500 to-emerald-400',iconBg: 'bg-emerald-500/10',iconColor: 'text-emerald-400' },
  'developer-agent': { border: 'hover:border-amber-500/30',  gradient: 'from-amber-500 to-amber-400',  iconBg: 'bg-amber-500/10',  iconColor: 'text-amber-400' },
  'gitlab-agent':    { border: 'hover:border-orange-500/30', gradient: 'from-orange-500 to-orange-400', iconBg: 'bg-orange-500/10', iconColor: 'text-orange-400' },
  'security-agent':  { border: 'hover:border-red-500/30',    gradient: 'from-red-500 to-red-400',      iconBg: 'bg-red-500/10',    iconColor: 'text-red-400' },
  'qa-agent':        { border: 'hover:border-cyan-500/30',   gradient: 'from-cyan-500 to-cyan-400',    iconBg: 'bg-cyan-500/10',   iconColor: 'text-cyan-400' },
  'devops-agent':    { border: 'hover:border-sky-500/30',    gradient: 'from-sky-500 to-sky-400',      iconBg: 'bg-sky-500/10',    iconColor: 'text-sky-400' },
};

const DEFAULT_ACCENT = { border: 'hover:border-teal-500/30', gradient: 'from-teal-500 to-teal-400', iconBg: 'bg-teal-500/10', iconColor: 'text-teal-400' };

export function AgentCard({ agent }: { agent: Agent }) {
  const accent = AGENT_ACCENTS[agent.name] ?? DEFAULT_ACCENT;

  return (
    <Link href={`/agents/${agent.id}`} className="group block">
      <Card className={cn(
        'relative h-full overflow-hidden border-white/[0.06] bg-card/80 p-4 transition-all duration-300 hover:bg-card hover:shadow-lg',
        accent.border,
      )}>
        {/* Top accent line */}
        <div className={cn('absolute left-0 top-0 h-[2px] w-full opacity-40 transition-opacity group-hover:opacity-80 bg-gradient-to-r', accent.gradient)} />

        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn('flex h-10 w-10 items-center justify-center rounded-lg ring-1 ring-inset ring-white/[0.08]', accent.iconBg)}>
              <Bot className={cn('h-5 w-5', accent.iconColor)} />
            </div>
            <div>
              <p className="font-semibold leading-tight text-foreground">
                {agent.displayName}
              </p>
              <p className="font-mono text-xs text-muted-foreground">{agent.name}</p>
            </div>
          </div>
          <StatusBadge status={agent.availability} size="sm" />
        </div>

        <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">{agent.role}</p>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {agent.mcpServers.slice(0, 3).map((s) => (
            <Badge key={s} variant="secondary" className="border-white/[0.06] bg-muted/60 font-normal">
              {s}
            </Badge>
          ))}
        </div>

        <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3 text-xs text-muted-foreground">
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
