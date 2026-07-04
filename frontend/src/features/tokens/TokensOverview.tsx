'use client';

import { ArrowRight, Coins } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/src/components/common/EmptyState';
import { useTelemetryOverview } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';
import { formatRelative } from '@/src/lib/format';
import { formatTokenCount } from '@/src/lib/token-display';

export function TokensOverview() {
  const { data: rows, isLoading } = useTelemetryOverview();
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
    );
  }

  if (!rows?.length) {
    return (
      <EmptyState
        icon={Coins}
        title="No pipeline runs yet"
        description="Submit a brief from the dashboard to start a run. Token usage will appear here per project."
      />
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((row) => (
        <button
          key={row.projectId}
          type="button"
          onClick={() => setTokensProjectId(row.projectId)}
          className="group text-left"
        >
          <Card className="h-full border-white/[0.06] bg-card/80 p-4 transition-all hover:border-teal-500/30 hover:bg-card">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate font-semibold text-foreground">{row.projectName}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {row.runCount} run{row.runCount === 1 ? '' : 's'} · last {formatRelative(row.lastRunAt)}
                </p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-colors group-hover:text-teal-400" />
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-sm">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Tokens</p>
                <p className="font-mono font-medium text-foreground">
                  {row.totalTokens > 0 ? formatTokenCount(row.totalTokens) : '—'}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Est. cost</p>
                <p className="font-medium text-foreground">
                  {row.costUsd > 0 ? `$${row.costUsd.toFixed(2)}` : '—'}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Agents</p>
                <p className="text-foreground">
                  {row.agentsWithTelemetry > 0 ? `${row.agentsWithTelemetry}/4` : '—'}
                </p>
              </div>
            </div>
          </Card>
        </button>
      ))}
    </div>
  );
}
