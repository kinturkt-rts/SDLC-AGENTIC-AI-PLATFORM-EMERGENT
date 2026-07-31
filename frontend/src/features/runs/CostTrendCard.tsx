'use client';

import {
  Bar,
  ComposedChart,
  CartesianGrid,
  Cell,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { LineChart as LineChartIcon } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { usePipelineTelemetry } from '@/src/lib/queries';
import { AGENT_CHART_COLOR, formatTokenCount } from '@/src/lib/token-display';

function shortAgentName(name: string): string {
  return name.replace(/ Agent$/, '');
}

interface Row {
  name: string;
  agentId: string;
  tokens: number;
  cost: number;
}

interface TooltipProps {
  active?: boolean;
  payload?: { payload: Row }[];
}

function ChartTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-lg border border-white/[0.08] bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-foreground">{row.name}</p>
      <p className="mt-1 text-muted-foreground">{formatTokenCount(row.tokens)} tokens billed</p>
      <p className="text-emerald-400">${row.cost.toFixed(4)} spend</p>
    </div>
  );
}

export function CostTrendCard({ projectId }: { projectId: string }) {
  const { data: telemetry, isLoading } = usePipelineTelemetry(projectId);

  if (isLoading) {
    return <Skeleton className="h-[320px] w-full rounded-xl" />;
  }

  const reporting = (telemetry?.agents ?? []).filter((a) => a.hasTelemetry);
  const data: Row[] = reporting.map((a) => ({
    name: shortAgentName(a.agentName),
    agentId: a.agentId,
    tokens: a.totalTokens,
    cost: Math.round(a.costUsd * 10000) / 10000,
  }));

  return (
    <Card className="border-white/[0.06] bg-card/80" data-testid="cost-trend-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <LineChartIcon className="h-4 w-4 text-teal-400" /> Cost &amp; token trend
        </h2>
        {telemetry ? (
          <span className="text-xs text-muted-foreground">
            {formatTokenCount(telemetry.totals.totalTokens)} tokens · ${telemetry.totals.costUsd.toFixed(2)} total
          </span>
        ) : null}
      </div>

      {data.length === 0 ? (
        <p className="px-4 py-10 text-center text-sm text-muted-foreground" data-testid="cost-trend-empty">
          No telemetry recorded for this run yet.
        </p>
      ) : (
        <div className="p-4">
          <p className="mb-3 text-[11px] text-muted-foreground">
            Spend and billed tokens across each agent phase, in pipeline order.
          </p>
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }} barCategoryGap="24%">
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                <XAxis
                  dataKey="name"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="tokens"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => formatTokenCount(Number(v))}
                />
                <YAxis
                  yAxisId="cost"
                  orientation="right"
                  tick={{ fill: 'rgb(52 211 153)', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => `$${Number(v).toFixed(2)}`}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar yAxisId="tokens" dataKey="tokens" radius={[4, 4, 0, 0]} maxBarSize={56}>
                  {data.map((entry) => (
                    <Cell key={entry.agentId} fill={AGENT_CHART_COLOR[entry.agentId] ?? 'hsl(173 58% 45%)'} />
                  ))}
                </Bar>
                <Line
                  yAxisId="cost"
                  type="monotone"
                  dataKey="cost"
                  stroke="rgb(52 211 153)"
                  strokeWidth={2}
                  dot={{ r: 3, fill: 'rgb(52 211 153)' }}
                  activeDot={{ r: 5 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="h-2 w-3 rounded-sm bg-teal-400" /> Tokens (bars)
            </span>
            <span className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <span className="h-0.5 w-3 rounded-sm bg-emerald-400" /> Spend USD (line)
            </span>
          </div>
        </div>
      )}
    </Card>
  );
}
