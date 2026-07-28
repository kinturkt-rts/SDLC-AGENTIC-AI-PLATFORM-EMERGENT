'use client';

import { Card } from '@/components/ui/card';
import { PIPELINE_MODELS } from '@/src/lib/token-display';
import { cn } from '@/lib/utils';

export function PipelineModelsBanner() {
  const sonnet = PIPELINE_MODELS.filter((m) => m.family === 'sonnet');
  const opus = PIPELINE_MODELS.filter((m) => m.family === 'opus');

  return (
    <Card className="border-white/[0.06] bg-card/80 p-4">
      <h2 className="text-sm font-semibold text-foreground">Pipeline LLM models</h2>
      <p className="mt-0.5 text-[11px] text-muted-foreground">
        Bedrock models for Product → Architect → Database → Developer
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:gap-4">
        <div className="flex flex-1 flex-wrap items-center gap-2 rounded-lg border border-blue-500/20 bg-blue-500/[0.04] px-3 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-400">Sonnet 4.6</span>
          {sonnet.map((m) => (
            <span
              key={m.agentId}
              className="rounded-md bg-muted/50 px-2 py-0.5 text-[11px] font-medium text-foreground"
            >
              {m.shortName}
            </span>
          ))}
        </div>
        <div className="flex flex-1 flex-wrap items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] px-3 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-400">Opus 4.6</span>
          {opus.map((m) => (
            <span
              key={m.agentId}
              className={cn(
                'rounded-md bg-muted/50 px-2 py-0.5 text-[11px] font-medium text-foreground',
              )}
            >
              {m.shortName}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
