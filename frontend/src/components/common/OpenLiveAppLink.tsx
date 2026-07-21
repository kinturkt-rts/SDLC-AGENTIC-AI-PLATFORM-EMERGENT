'use client';

import { ExternalLink, Rocket } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Uniform “Open live app” control — always opens in a new tab (same pattern as GitLab links). */
export function OpenLiveAppLink({
  href,
  className,
  variant = 'link',
}: {
  href: string;
  className?: string;
  /** `link` = text row (project overview); `button` = bordered CTA (run handoffs); `chip` = compact card footer */
  variant?: 'link' | 'button' | 'chip';
}) {
  const base =
    variant === 'button'
      ? 'inline-flex w-fit items-center gap-1.5 rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-1.5 text-sm font-medium text-sky-300 hover:bg-sky-500/15'
      : variant === 'chip'
        ? 'inline-flex items-center gap-1.5 rounded-md border border-sky-500/25 bg-sky-500/10 px-2 py-1 text-xs font-medium text-sky-300 hover:bg-sky-500/15'
        : 'inline-flex items-center gap-1.5 text-sm font-medium text-sky-300 hover:text-sky-200';

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={cn(base, className)}
      onClick={(e) => e.stopPropagation()}
    >
      {variant === 'chip' ? <Rocket className="h-3 w-3 opacity-80" /> : null}
      Open live app
      <ExternalLink className={variant === 'chip' ? 'h-3 w-3 opacity-70' : 'h-3.5 w-3.5 opacity-80'} />
    </a>
  );
}
