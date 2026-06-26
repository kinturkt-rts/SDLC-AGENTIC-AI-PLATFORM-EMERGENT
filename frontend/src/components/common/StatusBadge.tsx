import { cn } from '@/lib/utils';

type StatusConfig = { label: string; dot: string; text: string; bg: string; ring: string };

const STATUS_MAP: Record<string, StatusConfig> = {
  // RunStatus
  queued: { label: 'Queued', dot: 'bg-slate-400', text: 'text-slate-600 dark:text-slate-300', bg: 'bg-slate-100 dark:bg-slate-800/60', ring: 'ring-slate-200 dark:ring-slate-700' },
  running: { label: 'Running', dot: 'bg-blue-500 animate-pulse', text: 'text-blue-700 dark:text-blue-300', bg: 'bg-blue-50 dark:bg-blue-950/40', ring: 'ring-blue-200 dark:ring-blue-900' },
  paused: { label: 'Paused', dot: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-950/40', ring: 'ring-amber-200 dark:ring-amber-900' },
  completed: { label: 'Completed', dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-950/40', ring: 'ring-emerald-200 dark:ring-emerald-900' },
  failed: { label: 'Failed', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-950/40', ring: 'ring-red-200 dark:ring-red-900' },
  cancelled: { label: 'Cancelled', dot: 'bg-slate-400', text: 'text-slate-600 dark:text-slate-300', bg: 'bg-slate-100 dark:bg-slate-800/60', ring: 'ring-slate-200 dark:ring-slate-700' },
  // StepStatus extras
  waiting_for_human: { label: 'Waiting for human', dot: 'bg-amber-500 animate-pulse', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-950/40', ring: 'ring-amber-200 dark:ring-amber-900' },
  skipped: { label: 'Skipped', dot: 'bg-slate-300 dark:bg-slate-600', text: 'text-slate-500 dark:text-slate-400', bg: 'bg-slate-50 dark:bg-slate-800/40', ring: 'ring-slate-200 dark:ring-slate-700' },
  // Availability
  online: { label: 'Online', dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-950/40', ring: 'ring-emerald-200 dark:ring-emerald-900' },
  offline: { label: 'Offline', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-950/40', ring: 'ring-red-200 dark:ring-red-900' },
  unknown: { label: 'Unknown', dot: 'bg-slate-400', text: 'text-slate-600 dark:text-slate-300', bg: 'bg-slate-100 dark:bg-slate-800/60', ring: 'ring-slate-200 dark:ring-slate-700' },
  // MCP health
  healthy: { label: 'Healthy', dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-950/40', ring: 'ring-emerald-200 dark:ring-emerald-900' },
  degraded: { label: 'Degraded', dot: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-950/40', ring: 'ring-amber-200 dark:ring-amber-900' },
  down: { label: 'Down', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-950/40', ring: 'ring-red-200 dark:ring-red-900' },
  // Log levels
  info: { label: 'INFO', dot: 'bg-blue-500', text: 'text-blue-700 dark:text-blue-300', bg: 'bg-blue-50 dark:bg-blue-950/40', ring: 'ring-blue-200 dark:ring-blue-900' },
  warn: { label: 'WARN', dot: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-950/40', ring: 'ring-amber-200 dark:ring-amber-900' },
  error: { label: 'ERROR', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-950/40', ring: 'ring-red-200 dark:ring-red-900' },
  debug: { label: 'DEBUG', dot: 'bg-slate-400', text: 'text-slate-600 dark:text-slate-300', bg: 'bg-slate-100 dark:bg-slate-800/60', ring: 'ring-slate-200 dark:ring-slate-700' },
  // checkpoint
  pending: { label: 'Pending', dot: 'bg-amber-500 animate-pulse', text: 'text-amber-700 dark:text-amber-300', bg: 'bg-amber-50 dark:bg-amber-950/40', ring: 'ring-amber-200 dark:ring-amber-900' },
  approved: { label: 'Approved', dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-300', bg: 'bg-emerald-50 dark:bg-emerald-950/40', ring: 'ring-emerald-200 dark:ring-emerald-900' },
  rejected: { label: 'Rejected', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-300', bg: 'bg-red-50 dark:bg-red-950/40', ring: 'ring-red-200 dark:ring-red-900' },
};

const FALLBACK: StatusConfig = STATUS_MAP.unknown;

export function StatusBadge({
  status,
  label,
  className,
  size = 'md',
}: {
  status: string;
  label?: string;
  className?: string;
  size?: 'sm' | 'md';
}) {
  const cfg = STATUS_MAP[status] ?? FALLBACK;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset whitespace-nowrap',
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
        cfg.bg,
        cfg.text,
        cfg.ring,
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', cfg.dot)} />
      {label ?? cfg.label}
    </span>
  );
}
