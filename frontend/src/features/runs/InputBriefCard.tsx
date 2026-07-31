'use client';

import * as React from 'react';
import { ChevronDown, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useInputBrief } from '@/src/lib/queries';

export function InputBriefCard({ slug, runId }: { slug: string; runId?: string }) {
  const { data: brief, isLoading } = useInputBrief(slug, runId);
  const [open, setOpen] = React.useState(false);

  if (isLoading) {
    return <Skeleton className="h-14 w-full rounded-xl" />;
  }
  if (!brief?.content?.trim()) return null;

  return (
    <Card className="overflow-hidden border-white/[0.06] bg-card/80" data-testid="input-brief-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        data-testid="input-brief-toggle"
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-500/15 text-teal-400">
          <FileText className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-foreground">What was asked</span>
          <span className="block truncate text-xs text-muted-foreground">
            Original product brief · <span className="font-mono">{brief.path}</span>
          </span>
        </span>
        <ChevronDown
          className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
        />
      </button>
      {open ? (
        <div className="border-t border-white/[0.06] bg-black/20 px-4 py-3" data-testid="input-brief-content">
          <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-muted-foreground">
            {brief.content}
          </pre>
        </div>
      ) : null}
    </Card>
  );
}
