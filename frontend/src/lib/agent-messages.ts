import type {
  AgentMessage,
  AgentMessageType,
  AgentName,
  PipelineRun,
  PipelineStep,
  RunHandoffs,
  SdlcPhase,
} from '@/src/types';
import { TIMELINE_PHASES } from './pipeline-phases';

const ASSIGN_SUMMARY: Record<SdlcPhase, string> = {
  requirements: 'Generate the PRD and scope requirements from the product brief.',
  architecture: 'Produce the architecture doc and AWS diagram from the approved PRD.',
  data: 'Design the database schema and author the SQL migrations.',
  implementation: 'Implement the FastAPI application, routers and service layer.',
  frontend: 'Generate the React frontend from the OpenAPI contract.',
  qa: 'Run the integration and unit test suite before the deploy gate.',
  security: 'Run SAST and dependency scans before publishing.',
  publish: 'Publish the feature branch and open the merge request.',
  deploy: 'Deploy the published app to AWS and return a live URL.',
};

const RESULT_SUMMARY: Record<SdlcPhase, string> = {
  requirements: 'PRD delivered and requirements approved.',
  architecture: 'Architecture doc and system diagram produced.',
  data: 'SQL migrations generated and schema finalized.',
  implementation: 'FastAPI application code written and validated.',
  frontend: 'React frontend generated and validated against OpenAPI.',
  qa: 'Test suite executed and QA checks passed.',
  security: 'Security scan completed with no blocking findings.',
  publish: 'Branch published and merge request opened.',
  deploy: 'App deployed to AWS and reachable at its live URL.',
};

function shortId(runId: string): string {
  return runId.replace(/-/g, '').slice(0, 6);
}

function resultSummaryForPhase(phase: SdlcPhase, handoffs: RunHandoffs | null): string {
  if (phase === 'implementation' && handoffs?.developer) {
    const n = handoffs.developer.writtenFilesCount;
    if (n > 0) return `FastAPI application code written (${n} files).`;
  }
  if (phase === 'deploy' && handoffs?.gitlab) {
    const g = handoffs.gitlab;
    const parts: string[] = [];
    if (g.branch) parts.push(`branch ${g.branch}`);
    if (g.mergeRequestIid) parts.push(`MR !${g.mergeRequestIid}`);
    if (g.pathsPublishedCount) parts.push(`${g.pathsPublishedCount} paths`);
    const detail = parts.length ? ` (${parts.join(', ')})` : '';
    return `Published to GitLab${detail}.`;
  }
  return RESULT_SUMMARY[phase];
}

/** Derive phase-level A2A orchestration messages from a run's actual step timeline + handoffs. */
export function buildRunAgentMessages(
  run: PipelineRun,
  handoffs: RunHandoffs | null = null,
): AgentMessage[] {
  const messages: AgentMessage[] = [];
  const steps = run.steps.filter((s) => TIMELINE_PHASES.includes(s.phase));

  for (const step of steps as PipelineStep[]) {
    if (step.status === 'queued' || step.status === 'skipped') continue;

    const phase = step.phase;
    const agent = step.agent as AgentName;
    const correlationId = `cor-${phase}-${shortId(run.id)}`;
    const assignedAt = step.startedAt ?? run.startedAt;

    messages.push({
      id: `${run.id}-${phase}-assign`,
      type: 'task.assign',
      from: 'orchestrator-agent',
      to: agent,
      correlationId,
      runId: run.id,
      ts: assignedAt,
      summary: ASSIGN_SUMMARY[phase],
    });

    let type: AgentMessageType | null = null;
    let summary = '';
    let ts = step.finishedAt ?? assignedAt;

    if (step.status === 'completed') {
      type = 'task.result';
      summary = resultSummaryForPhase(phase, handoffs);
    } else if (step.status === 'failed') {
      type = 'task.error';
      summary = step.error ?? `${ASSIGN_SUMMARY[phase]} failed.`;
    } else if (step.status === 'running') {
      type = 'status.update';
      summary = 'Work in progress on this phase.';
      ts = assignedAt;
    } else if (step.status === 'waiting_for_human') {
      type = 'hitl.request';
      summary = 'Paused for human review before continuing.';
      ts = assignedAt;
    }

    if (type) {
      messages.push({
        id: `${run.id}-${phase}-${type}`,
        type,
        from: type === 'hitl.request' ? agent : agent,
        to: 'orchestrator-agent',
        correlationId,
        runId: run.id,
        ts,
        summary,
      });
    }
  }

  return messages.sort((a, b) => a.ts.localeCompare(b.ts));
}
