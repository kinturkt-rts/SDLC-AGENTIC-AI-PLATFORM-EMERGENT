import type { AgentName, PipelineStep, SdlcPhase, StepStatus } from '@/src/types';
import { formatRelative } from './format';

/** Agent responsible for each SDLC phase (timeline + run reconciliation). */
export const PHASE_AGENT: Record<SdlcPhase, AgentName> = {
  requirements: 'product-agent',
  architecture: 'architect-agent',
  data: 'database-agent',
  implementation: 'developer-agent',
  qa: 'qa-agent',
  security: 'security-agent',
  deploy: 'gitlab-agent',
};

/** Agents surfaced in logs / CloudWatch filters (MVP + orchestrator). */
export const MVP_LOG_AGENT_NAMES: AgentName[] = [
  'orchestrator-agent',
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'gitlab-agent',
  'qa-agent',
  'devops-agent',
  'security-agent',
];

export const MVP_LOG_AGENT_SET = new Set<string>(MVP_LOG_AGENT_NAMES);

export function parseLogAgentQuery(value: string | null | undefined): AgentName | undefined {
  const trimmed = value?.trim();
  return trimmed && MVP_LOG_AGENT_SET.has(trimmed) ? (trimmed as AgentName) : undefined;
}

/** User-facing labels for SDLC timeline phases. */
export const PHASE_DISPLAY_LABEL: Record<SdlcPhase, string> = {
  requirements: 'PRD',
  architecture: 'Architecture Diagram',
  data: 'Database',
  implementation: 'Application Code',
  qa: 'QA',
  security: 'Security',
  deploy: 'Publish',
};

/** Core MVP pipeline steps shown on the run detail timeline. */
export const MVP_TIMELINE_PHASES: SdlcPhase[] = [
  'requirements',
  'architecture',
  'data',
  'implementation',
  'deploy',
];

export function phaseDisplayLabel(phase: SdlcPhase | string | null | undefined): string {
  if (!phase) return 'Pipeline';
  return PHASE_DISPLAY_LABEL[phase as SdlcPhase] ?? phase;
}

export function stepStatusHint(step: PipelineStep): string {
  switch (step.status) {
    case 'running':
      return step.startedAt ? `started ${formatRelative(step.startedAt)}` : 'in progress';
    case 'completed':
      return step.finishedAt
        ? `completed ${formatRelative(step.finishedAt)}`
        : step.startedAt
          ? `started ${formatRelative(step.startedAt)}`
          : 'completed';
    case 'queued':
      return 'queued';
    case 'failed':
      return 'failed';
    case 'waiting_for_human':
      return 'awaiting approval';
    case 'skipped':
      return 'skipped';
    default:
      return 'not started';
  }
}
