'use client';

import Link from 'next/link';
import {
  Building2,
  Check,
  ChevronRight,
  Code2,
  Database,
  FileText,
  GitBranch,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { PHASE_DISPLAY_LABEL } from '@/src/lib/pipeline-phases';
import type { AgentName, PipelineRun, SdlcPhase } from '@/src/types';

const PIPELINE_NODES: {
  agentId: AgentName;
  label: string;
  shortLabel: string;
  phase: SdlcPhase;
  icon: LucideIcon;
  accent: string;
  activeBorder: string;
  activeBg: string;
  activeGlow: string;
}[] = [
  {
    agentId: 'product-agent',
    label: 'Product',
    shortLabel: PHASE_DISPLAY_LABEL.requirements,
    phase: 'requirements',
    icon: FileText,
    accent: 'text-blue-400',
    activeBorder: 'border-blue-500/45',
    activeBg: 'bg-blue-500/[0.08]',
    activeGlow: 'shadow-[0_0_20px_-6px_rgba(59,130,246,0.55)]',
  },
  {
    agentId: 'architect-agent',
    label: 'Architect',
    shortLabel: PHASE_DISPLAY_LABEL.architecture,
    phase: 'architecture',
    icon: Building2,
    accent: 'text-violet-400',
    activeBorder: 'border-violet-500/45',
    activeBg: 'bg-violet-500/[0.08]',
    activeGlow: 'shadow-[0_0_20px_-6px_rgba(139,92,246,0.55)]',
  },
  {
    agentId: 'database-agent',
    label: 'Database',
    shortLabel: PHASE_DISPLAY_LABEL.data,
    phase: 'data',
    icon: Database,
    accent: 'text-emerald-400',
    activeBorder: 'border-emerald-500/45',
    activeBg: 'bg-emerald-500/[0.08]',
    activeGlow: 'shadow-[0_0_20px_-6px_rgba(16,185,129,0.55)]',
  },
  {
    agentId: 'developer-agent',
    label: 'Developer',
    shortLabel: PHASE_DISPLAY_LABEL.implementation,
    phase: 'implementation',
    icon: Code2,
    accent: 'text-amber-400',
    activeBorder: 'border-amber-500/45',
    activeBg: 'bg-amber-500/[0.08]',
    activeGlow: 'shadow-[0_0_20px_-6px_rgba(245,158,11,0.55)]',
  },
  {
    agentId: 'gitlab-agent',
    label: 'GitLab',
    shortLabel: PHASE_DISPLAY_LABEL.deploy,
    phase: 'deploy',
    icon: GitBranch,
    accent: 'text-orange-400',
    activeBorder: 'border-orange-500/45',
    activeBg: 'bg-orange-500/[0.08]',
    activeGlow: 'shadow-[0_0_20px_-6px_rgba(249,115,22,0.55)]',
  },
];

const PHASE_ORDER = PIPELINE_NODES.map((n) => n.phase);

type NodeVisual = 'active' | 'completed' | 'waiting' | 'idle';

interface NodeState {
  visual: NodeVisual;
  /** Apps currently executing on this agent. */
  busyOn: { runId: string; projectName: string }[];
  /** Active runs that already finished this stage. */
  completedOn: { runId: string; projectName: string }[];
}

function isLiveRun(run: PipelineRun): boolean {
  return run.status === 'running' || run.status === 'paused';
}

function nodeStateForAgent(agentId: AgentName, phase: SdlcPhase, liveRuns: PipelineRun[]): NodeState {
  const busyOn: NodeState['busyOn'] = [];
  const completedOn: NodeState['completedOn'] = [];
  const phaseIdx = PHASE_ORDER.indexOf(phase);

  for (const run of liveRuns) {
    const step = run.steps?.find((s) => s.agent === agentId || s.phase === phase);
    const projectName = run.projectName || run.projectId || 'unknown';
    const stepDone =
      step?.status === 'completed' || step?.status === 'skipped' || step?.status === 'failed';
    const stepBusy =
      step?.status === 'running' || step?.status === 'waiting_for_human';
    const isCurrent =
      !stepDone && (run.currentAgent === agentId || run.currentPhase === phase);

    if (stepBusy || isCurrent) {
      busyOn.push({ runId: run.id, projectName });
      continue;
    }

    if (step?.status === 'completed') {
      completedOn.push({ runId: run.id, projectName });
      continue;
    }

    const currentIdx = run.currentPhase ? PHASE_ORDER.indexOf(run.currentPhase) : -1;
    if (currentIdx >= 0 && phaseIdx >= 0 && phaseIdx < currentIdx) {
      completedOn.push({ runId: run.id, projectName });
    }
  }

  if (busyOn.length > 0) return { visual: 'active', busyOn, completedOn };
  if (liveRuns.length === 0) return { visual: 'idle', busyOn, completedOn };
  if (completedOn.length > 0) return { visual: 'completed', busyOn, completedOn };
  return { visual: 'waiting', busyOn, completedOn };
}

function busyCaption(busyOn: NodeState['busyOn']): string {
  if (busyOn.length === 0) return '';
  const names = [...new Set(busyOn.map((b) => b.projectName))];
  if (names.length === 1) return `running on ${names[0]}`;
  if (names.length === 2) return `on ${names[0]}, ${names[1]}`;
  return `on ${names[0]} +${names.length - 1}`;
}

export function PipelinePositionMap({ runs }: { runs: PipelineRun[] | undefined }) {
  const liveRuns = (runs ?? []).filter(isLiveRun);
  const hasLive = liveRuns.length > 0;

  return (
    <div className="mb-6 overflow-hidden rounded-xl border border-white/[0.06] bg-card/60">
      <div className="flex flex-col gap-1 border-b border-white/[0.06] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-foreground">Pipeline position</p>
          <p className="text-xs text-muted-foreground">
            Where active runs sit in the SDLC chain
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {hasLive
            ? `${liveRuns.length} active run${liveRuns.length === 1 ? '' : 's'}`
            : 'No active runs — stages idle'}
        </p>
      </div>

      <div className="overflow-x-auto px-3 py-4">
        <div className="flex min-w-[640px] items-stretch justify-between gap-1">
          {PIPELINE_NODES.map((node, idx) => {
            const state = nodeStateForAgent(node.agentId, node.phase, liveRuns);
            const Icon = node.icon;
            const isActive = state.visual === 'active';
            const isCompleted = state.visual === 'completed';
            const isWaiting = state.visual === 'waiting';
            const caption = isActive
              ? busyCaption(state.busyOn)
              : isCompleted
                ? 'completed'
                : isWaiting
                  ? 'waiting'
                  : 'idle';

            return (
              <div key={node.agentId} className="flex flex-1 items-center">
                <Link
                  href={`/agents/${node.agentId}`}
                  className={cn(
                    'group relative flex min-h-[108px] flex-1 flex-col items-center gap-2 rounded-xl border p-3 transition-all duration-300',
                    isActive && cn(node.activeBorder, node.activeBg, node.activeGlow),
                    isCompleted && 'border-emerald-500/25 bg-emerald-500/[0.04]',
                    isWaiting && 'border-white/[0.08] bg-white/[0.02]',
                    state.visual === 'idle' && 'border-white/[0.06] bg-white/[0.01] hover:border-white/[0.12]',
                  )}
                >
                  {isActive && (
                    <span className="absolute -top-1.5 right-2 rounded-full bg-amber-500 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                      Live
                    </span>
                  )}
                  {isCompleted && (
                    <span className="absolute -top-1.5 right-2 inline-flex items-center gap-0.5 rounded-full bg-emerald-500/85 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                      <Check className="h-2.5 w-2.5" /> Done
                    </span>
                  )}
                  {isWaiting && (
                    <span className="absolute -top-1.5 right-2 rounded-full bg-white/15 px-1.5 py-0.5 text-[9px] font-bold uppercase text-muted-foreground">
                      Wait
                    </span>
                  )}

                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-lg ring-1 ring-inset transition-all',
                      isActive && 'animate-pulse-glow bg-amber-500/15 ring-amber-500/35',
                      isCompleted && 'bg-emerald-500/10 ring-emerald-500/25',
                      !isActive && !isCompleted && 'bg-muted/40 ring-white/[0.08]',
                    )}
                  >
                    <Icon
                      className={cn(
                        'h-5 w-5',
                        isActive ? 'text-amber-300' : isCompleted ? 'text-emerald-400' : node.accent,
                      )}
                    />
                  </div>

                  <div className="text-center">
                    <p
                      className={cn(
                        'text-xs font-semibold',
                        isActive ? 'text-amber-200' : isCompleted ? 'text-emerald-300' : 'text-foreground',
                      )}
                    >
                      {node.label}
                    </p>
                    <p className="text-[10px] text-muted-foreground">{node.shortLabel}</p>
                  </div>

                  <p
                    className={cn(
                      'line-clamp-2 max-w-[9.5rem] text-center text-[10px] leading-snug',
                      isActive ? 'font-medium text-amber-200/90' : 'text-muted-foreground',
                    )}
                    title={caption}
                  >
                    {caption}
                  </p>

                  {isActive && state.busyOn.length > 0 && (
                    <div className="flex flex-wrap justify-center gap-1">
                      {[...new Set(state.busyOn.map((b) => b.projectName))].slice(0, 2).map((name) => (
                        <span
                          key={name}
                          className="max-w-[7rem] truncate rounded-md bg-amber-500/15 px-1.5 py-0.5 font-mono text-[9px] text-amber-200/90 ring-1 ring-amber-500/25"
                        >
                          {name}
                        </span>
                      ))}
                    </div>
                  )}
                </Link>

                {idx < PIPELINE_NODES.length - 1 && (
                  <div className="relative mx-0.5 flex h-[2px] w-6 shrink-0 items-center sm:w-8 lg:w-10">
                    <div
                      className={cn(
                        'h-full w-full rounded-full',
                        isCompleted ? 'bg-emerald-500/40' : isActive ? 'bg-amber-500/35' : 'bg-white/[0.08]',
                      )}
                    />
                    {isActive && <div className="pipeline-connector absolute inset-0" />}
                    <ChevronRight
                      className={cn(
                        'absolute -right-1 h-3 w-3',
                        isCompleted ? 'text-emerald-500/60' : isActive ? 'text-amber-400/70' : 'text-white/20',
                      )}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {hasLive && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 border-t border-white/[0.06] px-4 py-2.5 text-[11px] text-muted-foreground">
          {liveRuns.map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="hover:text-foreground"
            >
              <span className="font-medium text-foreground/80">{run.projectName}</span>
              {' · '}
              {run.currentAgent
                ? run.currentAgent.replace(/-agent$/, '')
                : run.currentPhase ?? 'running'}
              {' · '}
              <span className="font-mono">{run.id.slice(0, 8)}…</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
