import { Send, CheckCircle2, XCircle, Activity, UserCheck, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { AgentMessageType } from '@/src/types';

const MAP: Record<AgentMessageType, { label: string; icon: typeof Send; cls: string }> = {
  'task.assign': { label: 'task.assign', icon: Send, cls: 'bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:ring-blue-900' },
  'task.result': { label: 'task.result', icon: CheckCircle2, cls: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900' },
  'task.error': { label: 'task.error', icon: XCircle, cls: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900' },
  'status.update': { label: 'status.update', icon: Activity, cls: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800/60 dark:text-slate-300 dark:ring-slate-700' },
  'hitl.request': { label: 'hitl.request', icon: UserCheck, cls: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900' },
  'hitl.resolved': { label: 'hitl.resolved', icon: Check, cls: 'bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:ring-teal-900' },
};

export function MessageTypeBadge({ type }: { type: AgentMessageType }) {
  const cfg = MAP[type];
  const Icon = cfg.icon;
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] font-medium ring-1 ring-inset', cfg.cls)}>
      <Icon className="h-3 w-3" /> {cfg.label}
    </span>
  );
}
