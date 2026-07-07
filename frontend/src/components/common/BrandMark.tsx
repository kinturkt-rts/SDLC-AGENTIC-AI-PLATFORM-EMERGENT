import { Network } from 'lucide-react';
import { cn } from '@/lib/utils';

/** Sidebar / shell mark - orchestrator hub coordinating SDLC specialist agents. */
export function BrandMark({
  className,
  iconClassName,
}: {
  className?: string;
  iconClassName?: string;
}) {
  return (
    <div
      className={cn(
        'relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-teal-500 to-teal-600 text-white shadow-lg shadow-teal-500/20',
        className,
      )}
    >
      <Network className={cn('h-4 w-4', iconClassName)} strokeWidth={2.25} aria-hidden />
    </div>
  );
}
