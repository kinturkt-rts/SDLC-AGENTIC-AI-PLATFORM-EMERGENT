import { PHASE_DISPLAY_LABEL } from '@/src/lib/pipeline-phases';
import type { AgentMessage, PipelineRun, PipelineStep } from '@/src/types';

/**
 * Derive orchestration-bus messages from live pipeline runs.
 * This is a read-only view of phase handoffs (orchestrator ↔ specialist) —
 * not a separate A2A message store. Does not invoke agents or change runs.
 */
export function messagesFromRun(run: PipelineRun): AgentMessage[] {
  const messages: AgentMessage[] = [];
  const runKey = run.id.slice(0, 8);

  for (const step of run.steps) {
    if (step.status === 'queued') continue;
    messages.push(...messagesFromStep(run, step, runKey));
  }

  return messages;
}

function messagesFromStep(run: PipelineRun, step: PipelineStep, runKey: string): AgentMessage[] {
  const phaseLabel = PHASE_DISPLAY_LABEL[step.phase] ?? step.phase;
  const correlationId = `cor-${step.phase}-${runKey}`;
  const project = run.projectName || run.projectId;
  const out: AgentMessage[] = [];

  const assignTs = step.startedAt ?? run.startedAt;
  out.push({
    id: `msg-assign-${run.id}-${step.phase}`,
    type: 'task.assign',
    from: 'orchestrator-agent',
    to: step.agent,
    correlationId,
    runId: run.id,
    ts: assignTs,
    summary: `Assign ${phaseLabel} for ${project}.`,
  });

  if (step.status === 'running') {
    out.push({
      id: `msg-status-${run.id}-${step.phase}`,
      type: 'status.update',
      from: step.agent,
      to: 'orchestrator-agent',
      correlationId,
      runId: run.id,
      ts: step.startedAt ?? run.startedAt,
      summary: `${phaseLabel} in progress for ${project}.`,
    });
  }

  if (step.status === 'completed') {
    const doneTs = step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt;
    const duration =
      step.durationSec != null && step.durationSec > 0
        ? ` (${Math.round(step.durationSec)}s)`
        : '';
    out.push({
      id: `msg-result-${run.id}-${step.phase}`,
      type: 'task.result',
      from: step.agent,
      to: 'orchestrator-agent',
      correlationId,
      runId: run.id,
      ts: doneTs,
      summary: `${phaseLabel} completed for ${project}${duration}.`,
    });
  }

  if (step.status === 'failed') {
    const failTs = step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt;
    const err = step.error?.trim() || run.error?.trim();
    out.push({
      id: `msg-error-${run.id}-${step.phase}`,
      type: 'task.error',
      from: step.agent,
      to: 'orchestrator-agent',
      correlationId,
      runId: run.id,
      ts: failTs,
      summary: err
        ? `${phaseLabel} failed for ${project}: ${err.slice(0, 160)}`
        : `${phaseLabel} failed for ${project}.`,
    });
  }

  return out;
}

/** Newest first. Caps volume for the message log UI. */
export function listAgentMessagesFromRuns(
  runs: PipelineRun[],
  options?: { maxRuns?: number; correlationId?: string },
): AgentMessage[] {
  const maxRuns = options?.maxRuns ?? 25;
  const sortedRuns = [...runs]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, maxRuns);

  let messages = sortedRuns.flatMap(messagesFromRun);
  if (options?.correlationId) {
    messages = messages.filter((m) => m.correlationId === options.correlationId);
  }

  return messages.sort((a, b) => b.ts.localeCompare(a.ts));
}
