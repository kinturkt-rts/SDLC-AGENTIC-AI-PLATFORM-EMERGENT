import type { RunEvent } from '@/src/types';
import { secsAgo, minsAgo } from './time';

// Discriminated run event stream per run. Structured so this can be replaced by a
// real SSE/WebSocket subscription (GET /runs/:id/events) without UI changes.
export const mockRunEvents: Record<string, RunEvent[]> = {
  'run-8f2a91': [
    { id: 'ev-8f-1', runId: 'run-8f2a91', kind: 'phase.started', ts: minsAgo(40), phase: 'requirements', agent: 'product-agent' },
    { id: 'ev-8f-2', runId: 'run-8f2a91', kind: 'agent.message', ts: minsAgo(40), from: 'orchestrator-agent', to: 'product-agent', messageType: 'task.assign', summary: 'Generate PRD (v1 scope).' },
    { id: 'ev-8f-3', runId: 'run-8f2a91', kind: 'artifact.created', ts: minsAgo(38), agent: 'product-agent', artifactName: 'PRD.md', artifactKind: 'prd' },
    { id: 'ev-8f-4', runId: 'run-8f2a91', kind: 'hitl.requested', ts: minsAgo(35), phase: 'requirements', agent: 'product-agent', checkpointId: 'hitl-002', title: 'Sign off on PRD scope for v1' },
    { id: 'ev-8f-5', runId: 'run-8f2a91', kind: 'phase.completed', ts: minsAgo(34), phase: 'requirements', agent: 'product-agent', durationSec: 360 },
    { id: 'ev-8f-6', runId: 'run-8f2a91', kind: 'phase.started', ts: minsAgo(34), phase: 'architecture', agent: 'architect-agent' },
    { id: 'ev-8f-7', runId: 'run-8f2a91', kind: 'artifact.created', ts: minsAgo(31), agent: 'architect-agent', artifactName: 'system-diagram.png', artifactKind: 'diagram' },
    { id: 'ev-8f-8', runId: 'run-8f2a91', kind: 'phase.completed', ts: minsAgo(31), phase: 'architecture', agent: 'architect-agent', durationSec: 180 },
    { id: 'ev-8f-9', runId: 'run-8f2a91', kind: 'phase.started', ts: minsAgo(28), phase: 'data', agent: 'database-agent' },
    { id: 'ev-8f-10', runId: 'run-8f2a91', kind: 'artifact.created', ts: minsAgo(24), agent: 'database-agent', artifactName: '0001_init_schema.sql', artifactKind: 'migration' },
    { id: 'ev-8f-11', runId: 'run-8f2a91', kind: 'phase.completed', ts: minsAgo(24), phase: 'data', agent: 'database-agent', durationSec: 240 },
    { id: 'ev-8f-12', runId: 'run-8f2a91', kind: 'phase.started', ts: minsAgo(10), phase: 'implementation', agent: 'developer-agent' },
    { id: 'ev-8f-13', runId: 'run-8f2a91', kind: 'log', ts: secsAgo(120), level: 'info', agent: 'developer-agent', message: 'Scaffolding FastAPI router app/routers/budgets.py' },
    { id: 'ev-8f-14', runId: 'run-8f2a91', kind: 'log', ts: secsAgo(30), level: 'debug', agent: 'developer-agent', message: 'MCP gitlab.repo.commit -> sha 9f2c1a' },
  ],
  'run-3c77d0': [
    { id: 'ev-3c-1', runId: 'run-3c77d0', kind: 'phase.completed', ts: minsAgo(80), phase: 'qa', agent: 'qa-agent', durationSec: 540 },
    { id: 'ev-3c-2', runId: 'run-3c77d0', kind: 'phase.started', ts: minsAgo(25), phase: 'security', agent: 'security-agent' },
    { id: 'ev-3c-3', runId: 'run-3c77d0', kind: 'agent.message', ts: minsAgo(20), from: 'orchestrator-agent', to: 'security-agent', messageType: 'task.assign', summary: 'Run SAST + dependency scan.' },
    { id: 'ev-3c-4', runId: 'run-3c77d0', kind: 'log', ts: minsAgo(19), level: 'warn', agent: 'security-agent', message: '2 medium findings detected (insecure deserialization, weak JWT expiry)' },
    { id: 'ev-3c-5', runId: 'run-3c77d0', kind: 'hitl.requested', ts: minsAgo(18), phase: 'security', agent: 'security-agent', checkpointId: 'hitl-001', title: 'Approve security scan with 2 medium findings' },
  ],
  'run-1a40be': [
    { id: 'ev-1a-1', runId: 'run-1a40be', kind: 'phase.completed', ts: minsAgo(210), phase: 'implementation', agent: 'developer-agent', durationSec: 600 },
    { id: 'ev-1a-2', runId: 'run-1a40be', kind: 'phase.completed', ts: minsAgo(200), phase: 'qa', agent: 'qa-agent', durationSec: 480 },
    { id: 'ev-1a-3', runId: 'run-1a40be', kind: 'artifact.created', ts: minsAgo(185), agent: 'security-agent', artifactName: 'security-scan.sarif', artifactKind: 'scan' },
    { id: 'ev-1a-4', runId: 'run-1a40be', kind: 'hitl.requested', ts: minsAgo(184), phase: 'security', agent: 'security-agent', checkpointId: 'hitl-004', title: 'Approve production deploy' },
    { id: 'ev-1a-5', runId: 'run-1a40be', kind: 'agent.message', ts: minsAgo(184), from: 'orchestrator-agent', to: 'security-agent', messageType: 'hitl.resolved', summary: 'Production deploy approved by s.patel.' },
    { id: 'ev-1a-6', runId: 'run-1a40be', kind: 'artifact.created', ts: minsAgo(181), agent: 'devops-agent', artifactName: 'main.tf', artifactKind: 'cicd' },
    { id: 'ev-1a-7', runId: 'run-1a40be', kind: 'phase.completed', ts: minsAgo(180), phase: 'deploy', agent: 'devops-agent', durationSec: 300 },
  ],
  'run-9b51cc': [
    { id: 'ev-9b-1', runId: 'run-9b51cc', kind: 'phase.started', ts: minsAgo(112), phase: 'qa', agent: 'qa-agent' },
    { id: 'ev-9b-2', runId: 'run-9b51cc', kind: 'agent.message', ts: minsAgo(112), from: 'orchestrator-agent', to: 'qa-agent', messageType: 'task.assign', summary: 'Execute integration suite.' },
    { id: 'ev-9b-3', runId: 'run-9b51cc', kind: 'step.failed', ts: minsAgo(96), phase: 'qa', agent: 'qa-agent', error: 'test_alert_dispatch failed (flaky timeout)' },
  ],
};
