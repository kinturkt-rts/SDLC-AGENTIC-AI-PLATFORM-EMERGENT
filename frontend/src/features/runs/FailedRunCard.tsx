'use client';

import * as React from 'react';
import { AlertTriangle, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { parseRunValidationError } from '@/src/lib/run-error-display';

export function FailedRunCard({ error }: { error?: string | null }) {
  const [showRaw, setShowRaw] = React.useState(false);
  const parsed = parseRunValidationError(error);

  return (
    <Card className="border-red-500/30 bg-red-500/[0.05] p-4">
      <div className="flex items-start gap-3">
        <span className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-red-500/15 text-red-400">
          <AlertTriangle className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">Pipeline failed</p>
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            {parsed?.summary ?? error ?? 'See the phase timeline and event stream below for details.'}
          </p>
          {parsed && parsed.bullets.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px] leading-relaxed text-muted-foreground">
              {parsed.bullets.map((bullet, i) => (
                <li key={i}>{bullet}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
      {parsed && error ? (
        <div className="mt-3 border-t border-red-500/10 pt-2">
          <button
            type="button"
            onClick={() => setShowRaw((v) => !v)}
            aria-expanded={showRaw}
            className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground hover:text-foreground"
          >
            <ChevronDown className={cn('h-3.5 w-3.5 transition-transform', showRaw && 'rotate-180')} />
            {showRaw ? 'Hide raw output' : 'Show raw output'}
          </button>
          {showRaw ? (
            <pre className="mt-2 max-h-[300px] overflow-auto whitespace-pre-wrap break-words rounded-md bg-black/20 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {error}
            </pre>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
