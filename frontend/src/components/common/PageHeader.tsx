import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  toolbar,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  /** Full-width filter row below the title (use for multi-control toolbars). */
  toolbar?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('relative', className)}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            {eyebrow && (
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-teal-500">
                {eyebrow}
              </p>
            )}
            <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">{title}</h1>
          </div>
          {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
        </div>
        {description ? (
          <div className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</div>
        ) : null}
        {toolbar && <div className="flex flex-wrap items-center gap-2">{toolbar}</div>}
      </div>
      <div className="mt-4 h-px bg-gradient-to-r from-teal-500/20 via-border to-transparent" />
    </div>
  );
}
