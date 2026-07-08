import { MVP_TIMELINE_PHASES, PHASE_AGENT, phaseDisplayLabel } from './pipeline-phases';
import { parseLogTerminalStatus } from './run-reconcile';
import type {
  AgentName,
  ArtifactKind,
  PipelineRun,
  RunEvent,
  RunStatus,
  SdlcPhase,
} from '@/src/types';

export interface S3ArtifactRef {
  relPath: string;
  lastModified: string;
  sizeKb?: number;
}

export interface ActivityFeedItem {
  id: string;
  runId: string;
  projectName: string;
  agent: string;
  agentId: AgentName;
  description: string;
  ts: string;
  href: string;
  accent: string;
  /** Live streams only — no synthesized lifecycle rows in the dashboard feed. */
  stream?: 'cloudwatch' | 'artifact' | 'pipeline-log';
}

const AGENT_LABEL: Record<string, string> = {
  'orchestrator-agent': 'Orchestrator',
  'product-agent': 'Product Agent',
  'architect-agent': 'Architect Agent',
  'database-agent': 'Database Agent',
  'developer-agent': 'Developer Agent',
  'gitlab-agent': 'GitLab Agent',
  'qa-agent': 'QA Agent',
};

export const AGENT_ACTIVITY_ACCENT: Record<string, string> = {
  'orchestrator-agent': 'text-teal-400',
  'product-agent': 'text-blue-400',
  'architect-agent': 'text-violet-400',
  'database-agent': 'text-emerald-400',
  'developer-agent': 'text-amber-400',
  'gitlab-agent': 'text-orange-400',
  'qa-agent': 'text-slate-400',
};

function artifactKindForRel(relPath: string): ArtifactKind {
  const lower = relPath.toLowerCase();
  if (lower.includes('/prd/') && lower.endsWith('.md')) return 'prd';
  if (lower.includes('/design/') && lower.endsWith('.md')) return 'architecture';
  if (lower.includes('/diagrams/') && (lower.endsWith('.png') || lower.endsWith('.svg'))) return 'diagram';
  if (lower.includes('/db/sql/') && lower.endsWith('.sql')) return 'migration';
  if (lower.includes('gitlab-handoff')) return 'doc';
  if (lower.endsWith('.py') || lower.endsWith('requirements.txt')) return 'code';
  return 'doc';
}

function producerForKind(kind: ArtifactKind, relPath: string): AgentName {
  const lower = relPath.toLowerCase();
  if (kind === 'migration' || lower.includes('/db/')) return 'database-agent';
  if (kind === 'prd') return 'product-agent';
  if (kind === 'architecture' || kind === 'diagram') return 'architect-agent';
  if (kind === 'code') return 'developer-agent';
  if (lower.includes('gitlab-handoff')) return 'gitlab-agent';
  return 'product-agent';
}

function phaseForRel(relPath: string): SdlcPhase | null {
  const lower = relPath.toLowerCase();
  if (lower.includes('/prd/') && lower.endsWith('.md')) return 'requirements';
  if ((lower.includes('/design/') && lower.endsWith('.md')) || lower.includes('/diagrams/')) {
    return 'architecture';
  }
  if (lower.includes('/db/sql/') && lower.endsWith('.sql')) return 'data';
  if (lower.endsWith('.py') || lower.endsWith('requirements.txt') || lower.includes('/app/')) {
    return 'implementation';
  }
  if (lower.includes('gitlab-handoff')) return 'deploy';
  return null;
}

function artifactDescription(kind: ArtifactKind, name: string): string {
  switch (kind) {
    case 'prd':
      return `PRD published - ${name}`;
    case 'architecture':
      return `Architecture doc ready - ${name}`;
    case 'diagram':
      return `Diagram exported - ${name}`;
    case 'migration':
      return `SQL migration generated - ${name}`;
    case 'code':
      return `Application code - ${name}`;
    default:
      return `Artifact created - ${name}`;
  }
}

/** Build timeline events from S3 artifact timestamps (primary signal for cloud runs). */
export function buildS3ArtifactEvents(
  runId: string,
  artifacts: S3ArtifactRef[],
  startId = 0,
): RunEvent[] {
  const events: RunEvent[] = [];
  let i = startId;
  const phaseFirstTs = new Map<SdlcPhase, string>();

  const sorted = [...artifacts].sort((a, b) => a.lastModified.localeCompare(b.lastModified));

  for (const file of sorted) {
    const name = file.relPath.split('/').pop() ?? file.relPath;
    const kind = artifactKindForRel(file.relPath);
    const agent = producerForKind(kind, file.relPath);
    const phase = phaseForRel(file.relPath);

    events.push({
      id: `ev-s3-art-${runId}-${i++}`,
      runId,
      kind: 'artifact.created',
      ts: file.lastModified,
      agent,
      artifactName: name,
      artifactKind: kind,
    });

    if (phase && !phaseFirstTs.has(phase)) {
      phaseFirstTs.set(phase, file.lastModified);
      events.push({
        id: `ev-s3-phase-${runId}-${i++}`,
        runId,
        kind: 'phase.completed',
        ts: file.lastModified,
        phase,
        agent: PHASE_AGENT[phase],
        durationSec: 0,
      });
    }
  }

  return events;
}

export function buildLogEvents(runId: string, log: string, startedAt: string, startId = 0): RunEvent[] {
  const events: RunEvent[] = [];
  let i = startId;
  const lines = log.split('\n').map((l) => l.trim()).filter(Boolean);

  for (const line of lines) {
    const agentMatch = line.match(/^\[([a-z-]+-agent)\]\s*(.*)$/);
    if (agentMatch) {
      events.push({
        id: `ev-log-${runId}-${i++}`,
        runId,
        kind: 'log',
        ts: startedAt,
        level: line.toLowerCase().includes('failed') ? 'error' : 'info',
        agent: agentMatch[1] as AgentName,
        message: agentMatch[2] || line,
      });
      continue;
    }
    if (line.startsWith('error:')) {
      events.push({
        id: `ev-log-${runId}-${i++}`,
        runId,
        kind: 'log',
        ts: startedAt,
        level: 'error',
        agent: 'orchestrator-agent',
        message: line,
      });
    }
  }

  const terminal = parseLogTerminalStatus(log);
  if (terminal?.status === 'completed') {
    events.push({
      id: `ev-log-done-${runId}`,
      runId,
      kind: 'log',
      ts: startedAt,
      level: 'info',
      agent: 'orchestrator-agent',
      message: 'Pipeline completed successfully',
    });
  } else if (terminal?.status === 'failed') {
    events.push({
      id: `ev-log-fail-${runId}`,
      runId,
      kind: 'log',
      ts: startedAt,
      level: 'error',
      agent: 'orchestrator-agent',
      message: terminal.error ?? 'Pipeline failed',
    });
  }

  return events;
}

export function buildRunLifecycleEvents(run: PipelineRun, startId = 0): RunEvent[] {
  const events: RunEvent[] = [];
  let i = startId;

  events.push({
    id: `ev-life-start-${run.id}`,
    runId: run.id,
    kind: 'log',
    ts: run.startedAt,
    level: 'info',
    agent: 'orchestrator-agent',
    message: `Pipeline started for ${run.projectName}`,
  });

  if (run.status === 'completed' && run.finishedAt) {
    events.push({
      id: `ev-life-done-${run.id}`,
      runId: run.id,
      kind: 'log',
      ts: run.finishedAt,
      level: 'info',
      agent: 'orchestrator-agent',
      message: `Pipeline completed - ${run.projectName}`,
    });
  }

  if (run.status === 'failed') {
    events.push({
      id: `ev-life-fail-${run.id}`,
      runId: run.id,
      kind: 'log',
      ts: run.finishedAt ?? run.startedAt,
      level: 'error',
      agent: 'orchestrator-agent',
      message: run.error ?? `Pipeline failed - ${run.projectName}`,
    });
  }

  const failedSteps = run.steps.filter((s) => s.status === 'failed');
  for (const step of failedSteps) {
    events.push({
      id: `ev-step-fail-${run.id}-${step.phase}-${i++}`,
      runId: run.id,
      kind: 'step.failed',
      ts: step.finishedAt ?? step.startedAt ?? run.finishedAt ?? run.startedAt,
      phase: step.phase,
      agent: step.agent,
      error:
        step.error ??
        (run.error && failedSteps.length === 1
          ? run.error
          : 'Step did not complete successfully'),
    });
  }

  return events;
}

export function mergeRunEvents(...groups: RunEvent[][]): RunEvent[] {
  const byKey = new Map<string, RunEvent>();
  for (const group of groups) {
    for (const event of group) {
      byKey.set(event.id, event);
    }
  }
  return [...byKey.values()].sort((a, b) => b.ts.localeCompare(a.ts));
}

export function runEventToActivityFeed(
  run: PipelineRun,
  event: RunEvent,
  options?: { stream?: ActivityFeedItem['stream'] },
): ActivityFeedItem {
  const agentId =
    event.kind === 'agent.message'
      ? event.from
      : 'agent' in event
        ? event.agent
        : 'orchestrator-agent';

  let description = '';
  switch (event.kind) {
    case 'artifact.created':
      description = artifactDescription(event.artifactKind, event.artifactName);
      break;
    case 'phase.completed':
      description = `${phaseDisplayLabel(event.phase)} phase completed`;
      break;
    case 'phase.started':
      description = `${phaseDisplayLabel(event.phase)} phase in progress`;
      break;
    case 'step.failed':
      description = `Failed at ${phaseDisplayLabel(event.phase)} - ${event.error}`;
      break;
    case 'log':
      description = event.message;
      break;
    case 'agent.message':
      description = event.summary;
      break;
    case 'hitl.requested':
      description = event.title;
      break;
    default:
      description = 'Pipeline event';
  }

  const href = `/runs/${run.id}`;

  return {
    id: event.id,
    runId: run.id,
    projectName: run.projectName,
    agent: AGENT_LABEL[agentId] ?? agentId,
    agentId,
    description,
    ts: event.ts,
    href,
    accent: AGENT_ACTIVITY_ACCENT[agentId] ?? 'text-muted-foreground',
    stream: options?.stream,
  };
}

export function isTerminalRunStatus(status: RunStatus): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

/** Prefer S3-backed events for cloud; falls back to step/log signals. */
export function buildRunEvents(input: {
  run: PipelineRun;
  log: string | null;
  s3Artifacts: S3ArtifactRef[];
  latestActivityTs?: string;
}): RunEvent[] {
  let id = 0;
  const lifecycle = buildRunLifecycleEvents(input.run, id);
  id += lifecycle.length;

  const s3Events =
    input.s3Artifacts.length > 0
      ? buildS3ArtifactEvents(input.run.id, input.s3Artifacts, id)
      : [];
  id += s3Events.length;

  const logEvents = input.log ? buildLogEvents(input.run.id, input.log, input.run.startedAt, id) : [];

  const stepEvents: RunEvent[] = [];
  if (s3Events.length === 0) {
    for (const step of input.run.steps) {
      if (step.status === 'completed' && MVP_TIMELINE_PHASES.includes(step.phase)) {
        stepEvents.push({
          id: `ev-step-done-${input.run.id}-${step.phase}`,
          runId: input.run.id,
          kind: 'phase.completed',
          ts: step.finishedAt ?? input.run.startedAt,
          phase: step.phase,
          agent: step.agent,
          durationSec: step.durationSec ?? 0,
        });
      }
    }
  }

  const activeEvents: RunEvent[] = [];
  if (
    input.run.status === 'running' &&
    input.run.currentPhase &&
    input.run.currentAgent
  ) {
    activeEvents.push({
      id: `ev-active-${input.run.id}-${input.run.currentPhase}`,
      runId: input.run.id,
      kind: 'phase.started',
      ts: input.latestActivityTs ?? input.run.startedAt,
      phase: input.run.currentPhase,
      agent: input.run.currentAgent,
    });
  }

  return mergeRunEvents(lifecycle, s3Events, logEvents, stepEvents, activeEvents);
}
