'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '@/components/ui/card';
import { AGENT_CHART_COLOR, formatTokenCount } from '@/src/lib/token-display';
import type { AgentTelemetryRow } from '@/src/lib/pipeline-telemetry';

function shortAgentName(name: string): string {
  return name.replace(/ Agent$/, '');
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: { payload: { name: string; input: number; output: number; tokens: number; cost: number } }[];
}

function ChartTooltip({ active, payload }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-lg border border-white/[0.08] bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-foreground">{row.name}</p>
      <p className="mt-1 text-muted-foreground">
        {formatTokenCount(row.input)} in · {formatTokenCount(row.output)} out
      </p>
      <p className="text-muted-foreground">{formatTokenCount(row.tokens)} billed · ${row.cost.toFixed(2)}</p>
    </div>
  );
}

export function TokenUsageChart({ agents }: { agents: AgentTelemetryRow[] }) {
  const data = agents.map((a) => ({
    name: shortAgentName(a.agentName),
    agentId: a.agentId,
    input: a.inputTokens,
    output: a.outputTokens,
    tokens: a.totalTokens,
    cost: a.costUsd,
  }));

  return (
    <Card className="border-white/[0.06] bg-card/80 p-4">
      <h2 className="text-sm font-semibold text-foreground">Tokens by agent</h2>
      <p className="mt-0.5 text-[11px] text-muted-foreground">Billed tokens (input + output) per pipeline agent</p>
      <div className="mt-4 h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 4, left: -12, bottom: 0 }} barCategoryGap="20%">
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
            <XAxis
              dataKey="name"
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => formatTokenCount(Number(v))}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="tokens" radius={[4, 4, 0, 0]} maxBarSize={48}>
              {data.map((entry) => (
                <Cell
                  key={entry.agentId}
                  fill={AGENT_CHART_COLOR[entry.agentId] ?? 'hsl(173 58% 45%)'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        {data.map((entry) => (
          <span key={entry.agentId} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span
              className="h-2 w-2 rounded-sm"
              style={{ backgroundColor: AGENT_CHART_COLOR[entry.agentId] ?? 'hsl(173 58% 45%)' }}
            />
            {entry.name}
          </span>
        ))}
      </div>
    </Card>
  );
}
