import type { PipelineRun, PipelineStep, SdlcPhase, AgentName } from '@/src/types';
import { minsAgo, secsAgo } from './time';

const phaseAgent: Record<SdlcPhase, AgentName> = {
  requirements: 'product-agent',
  architecture: 'architect-agent',
  data: 'database-agent',
  implementation: 'developer-agent',
  qa: 'qa-agent',
  security: 'security-agent',
  deploy: 'devops-agent',
};

const PHASES: SdlcPhase[] = [
  'requirements',
  'architecture',
  'data',
  'implementation',
  'qa',
  'security',
  'deploy',
];

function buildSteps(
  runId: string,
  completedUpTo: number,
  currentStatus: 'running' | 'waiting_for_human' | 'failed' | 'completed' | null,
): PipelineStep[] {
  return PHASES.map((phase, idx) => {
    let status: PipelineStep['status'] = 'queued';
    if (idx < completedUpTo) status = 'completed';
    else if (idx === completedUpTo && currentStatus) status = currentStatus;
    const done = idx < completedUpTo;
    return {
      id: `${runId}-step-${idx}`,
      phase,
      agent: phaseAgent[phase],
      status,
      startedAt: idx <= completedUpTo ? minsAgo(40 - idx * 4) : null,
      finishedAt: done ? minsAgo(38 - idx * 4) : null,
      durationSec: done ? 90 + idx * 35 : null,
    };
  });
}

export const mockRuns: PipelineRun[] = [
  {
    id: 'run-8f2a91',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    pipeline: 'Standard SDLC',
    status: 'running',
    currentPhase: 'implementation',
    currentAgent: 'developer-agent',
    startedAt: minsAgo(41),
    finishedAt: null,
    elapsedSec: 41 * 60,
    triggeredBy: 'orchestrator-agent',
    steps: buildSteps('run-8f2a91', 3, 'running'),
  },
  {
    id: 'run-3c77d0',
    projectId: 'meeting-assistant',
    projectName: 'Meeting Assistant',
    pipeline: 'Standard SDLC',
    status: 'paused',
    currentPhase: 'security',
    currentAgent: 'security-agent',
    startedAt: minsAgo(120),
    finishedAt: null,
    elapsedSec: 65 * 60,
    triggeredBy: 'j.rivera',
    steps: buildSteps('run-3c77d0', 5, 'waiting_for_human'),
  },
  {
    id: 'run-1a40be',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    pipeline: 'Standard SDLC',
    status: 'completed',
    currentPhase: null,
    currentAgent: null,
    startedAt: minsAgo(220),
    finishedAt: minsAgo(180),
    elapsedSec: 40 * 60,
    triggeredBy: 'orchestrator-agent',
    steps: buildSteps('run-1a40be', 7, 'completed'),
  },
  {
    id: 'run-9b51cc',
    projectId: 'incident-triage-bot',
    projectName: 'Incident Triage Bot',
    pipeline: 'Hotfix',
    status: 'failed',
    currentPhase: 'qa',
    currentAgent: 'qa-agent',
    startedAt: minsAgo(110),
    finishedAt: minsAgo(95),
    elapsedSec: 15 * 60,
    triggeredBy: 'm.chen',
    steps: buildSteps('run-9b51cc', 4, 'failed'),
  },
  {
    id: 'run-2d09af',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    pipeline: 'Standard SDLC',
    status: 'running',
    currentPhase: 'requirements',
    currentAgent: 'product-agent',
    startedAt: secsAgo(95),
    finishedAt: null,
    elapsedSec: 95,
    triggeredBy: 'orchestrator-agent',
    steps: buildSteps('run-2d09af', 0, 'running'),
  },
  {
    id: 'run-7e63ba',
    projectId: 'demo-api',
    projectName: 'Demo API',
    pipeline: 'Standard SDLC',
    status: 'queued',
    currentPhase: null,
    currentAgent: null,
    startedAt: secsAgo(20),
    finishedAt: null,
    elapsedSec: 0,
    triggeredBy: 'a.kumar',
    steps: buildSteps('run-7e63ba', 0, null),
  },
];
