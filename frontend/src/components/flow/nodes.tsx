'use client';

import { Handle, Position } from '@xyflow/react';
import { Bot, UserCheck, Hexagon } from 'lucide-react';
import { cn } from '@/lib/utils';

const edgeHandle = '!h-2 !w-2 !border !border-border !bg-muted-foreground/50';
// Centered, invisible handle -> edges radiate from the node center (hub/spoke look).
const centerHandleStyle = { left: '50%', top: '50%', transform: 'translate(-50%, -50%)', opacity: 0 } as const;

export function PhaseNode({ data }: { data: { phase: string; agent: string; index: number } }) {
  return (
    <div className="w-[180px] rounded-lg border border-border bg-card p-3 shadow-sm">
      <Handle type="target" position={Position.Left} className={edgeHandle} />
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Phase {data.index + 1}</p>
      <p className="text-sm font-semibold capitalize text-foreground">{data.phase}</p>
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

const statusDot: Record<string, string> = {
  online: 'bg-emerald-500',
  offline: 'bg-red-500',
  unknown: 'bg-slate-400',
};

export function AgentNode({ data }: { data: { label: string; sub: string; status: string } }) {
  return (
    <div className="w-[150px] rounded-lg border border-border bg-card p-2.5 shadow-sm">
      <Handle type="target" position={Position.Left} style={centerHandleStyle} />
      <div className="flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <Bot className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{data.label}</p>
          <p className="truncate font-mono text-[10px] text-muted-foreground">{data.sub}</p>
        </div>
        <span className={cn('ml-auto h-2 w-2 shrink-0 rounded-full', statusDot[data.status] ?? statusDot.unknown)} />
      </div>
    </div>
  );
}

export function OrchestratorNode({ data }: { data: { label: string; sub: string } }) {
  return (
    <div className="w-[180px] rounded-xl border border-teal-400/60 bg-teal-500/10 p-3 text-center shadow-md ring-2 ring-teal-500/20">
      <Handle type="source" position={Position.Right} style={centerHandleStyle} />
      <div className="flex items-center justify-center gap-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-500 text-white">
          <Hexagon className="h-4 w-4" />
        </span>
        <div className="min-w-0 text-left">
          <p className="truncate text-sm font-bold text-foreground">{data.label}</p>
          <p className="truncate font-mono text-[10px] text-teal-700 dark:text-teal-300">{data.sub}</p>
        </div>
      </div>
    </div>
  );
}

export const pipelineNodeTypes = { phase: PhaseNode, gate: GateNode } as const;
export const orchestratorNodeTypes = { orchestrator: OrchestratorNode, agent: AgentNode } as const;
