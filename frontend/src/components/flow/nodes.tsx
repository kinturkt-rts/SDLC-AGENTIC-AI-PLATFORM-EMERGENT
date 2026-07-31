'use client';

import { Handle, Position } from '@xyflow/react';
import { Bot, UserCheck } from 'lucide-react';
import { phaseDisplayLabel } from '@/src/lib/pipeline-phases';

const edgeHandle = '!h-2 !w-2 !border !border-border !bg-muted-foreground/50';

export function PhaseNode({ data }: { data: { phase: string; agent: string; index: number } }) {
  return (
    <div className="w-[180px] rounded-lg border border-border bg-card p-3 shadow-sm">
      <Handle type="target" position={Position.Left} className={edgeHandle} />
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Phase {data.index + 1}</p>
      <p className="text-sm font-semibold text-foreground">{phaseDisplayLabel(data.phase)}</p>
      <div className="mt-1 flex items-center gap-1.5 text-xs text-teal-600 dark:text-teal-400">
        <Bot className="h-3 w-3" />
        <span className="truncate font-mono">{data.agent}</span>
      </div>
      <Handle type="source" position={Position.Right} className={edgeHandle} />
    </div>
  );
}

export function GateNode({ data }: { data: { phase: string } }) {
  return (
    <div className="w-[150px] rounded-lg border border-amber-300/70 bg-amber-50 p-2.5 text-center dark:border-amber-900/60 dark:bg-amber-950/30">
      <Handle type="target" position={Position.Left} className={edgeHandle} />
      <div className="flex items-center justify-center gap-1.5 text-amber-700 dark:text-amber-400">
        <UserCheck className="h-3.5 w-3.5" />
        <span className="text-xs font-semibold">HITL gate</span>
      </div>
      <p className="mt-0.5 text-[10px] capitalize text-amber-700/70 dark:text-amber-400/70">{data.phase} approval</p>
      <Handle type="source" position={Position.Right} className={edgeHandle} />
    </div>
  );
}

export const pipelineNodeTypes = { phase: PhaseNode, gate: GateNode } as const;
