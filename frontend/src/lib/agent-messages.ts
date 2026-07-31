import { PHASE_DISPLAY_LABEL } from '@/src/lib/pipeline-phases';
import { getRunArtifactEvents, isS3Store } from '@/src/lib/artifact-store';
import type { AgentMessage, PipelineRun, PipelineStep } from '@/src/types';

export async function messagesFromRun(run: PipelineRun): Promise<AgentMessage[]> {
  const runKey = run.id.slice(0, 8);
  const perStep = await Promise.all(
    run.steps.filter((step) => step.status !== 'queued').map((step) => messagesFromStep(run, step, runKey)),
  );
  return perStep.flat();
}

/** Real tool-call events the agent emitted live during this step, newest telemetry
 * first — [] for local mode, older runs, or steps that haven't called a tool yet. */
async function realToolCallMessages(
  run: PipelineRun,
  step: PipelineStep,
  correlationId: string,
): Promise<AgentMessage[]> {
  if (!isS3Store()) return [];
  const events = await getRunArtifactEvents(run.id, `${run.projectId}/events/${step.agent}.json`);
  return events
    .filter((e) => e.type === 'tool_call')
    .map((e, idx) => ({
      id: `msg-tool-${run.id}-${step.phase}-${String(e.seq ?? idx)}`,
      type: 'status.update' as const,
      from: step.agent,
      to: 'orchestrator-agent',
      correlationId,
      runId: run.id,
      ts: typeof e.ts === 'string' ? e.ts : (step.startedAt ?? run.startedAt),
      summary: `Tool call: ${String(e.tool ?? 'unknown')} (#${String(e.seq ?? idx + 1)})`,
    }));
}

async function messagesFromStep(run: PipelineRun, step: PipelineStep, runKey: string): Promise<AgentMessage[]> {
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
    const realEvents = await realToolCallMessages(run, step, correlationId);
    if (realEvents.length > 0) {
      out.push(...realEvents);
    } else {
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
export async function listAgentMessagesFromRuns(
  runs: PipelineRun[],
  options?: { maxRuns?: number; correlationId?: string },
): Promise<AgentMessage[]> {
  const maxRuns = options?.maxRuns ?? 25;
  const sortedRuns = [...runs]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, maxRuns);

  const perRun = await Promise.all(sortedRuns.map(messagesFromRun));
  let messages = perRun.flat();
  if (options?.correlationId) {
    messages = messages.filter((m) => m.correlationId === options.correlationId);
  }

  return messages.sort((a, b) => b.ts.localeCompare(a.ts));
}
