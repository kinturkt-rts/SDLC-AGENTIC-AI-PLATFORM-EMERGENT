import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.08] bg-card/40 px-6 py-14 text-center',
        className,
      )}
    >
      {Icon ? (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-muted/60 text-muted-foreground ring-1 ring-white/[0.06]">
          <Icon className="h-5 w-5" />
        </div>
      ) : null}
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      {description ? <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
