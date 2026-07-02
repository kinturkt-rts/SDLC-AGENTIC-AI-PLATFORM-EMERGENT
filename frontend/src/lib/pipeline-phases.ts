import type { PipelineStep, SdlcPhase, StepStatus } from '@/src/types';
import { formatRelative } from './format';

/** User-facing labels for SDLC timeline phases. */
export const PHASE_DISPLAY_LABEL: Record<SdlcPhase, string> = {
  requirements: 'PRD',
  architecture: 'Architecture Diagram',
  data: 'Database',
  implementation: 'Application',
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
