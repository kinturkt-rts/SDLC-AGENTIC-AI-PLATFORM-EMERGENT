import type { Project, PipelineDefinition } from '@/src/types';
import { minsAgo, daysAgo } from './time';

// Central project registry (mock phase).
// Each distinct target-app slug is one project. To add a project, append an entry here
// (or, in the real backend, it is discovered from agents/pipeline/<slug>.context.json).
// GET /api/v1/projects returns this same shape.
export const mockProjects: Project[] = [
  {
    id: 'finops-web-app',
    name: 'FinOps Web App',
    slug: 'finops-web-app',
    description: 'Cloud cost analytics & budgeting dashboard with anomaly alerts and chargeback reports.',
    pipelineStatus: 'running',
    artifactCount: 14,
    lastRunAt: minsAgo(2),
    repo: 'gitlab.com/acme/target-apps/finops-web-app',
    environment: 'staging',
  },
  {
    id: 'meeting-assistant',
    name: 'Meeting Assistant',
    slug: 'meeting-assistant',
    description: 'Real-time meeting transcription, action-item extraction, and summary delivery.',
    pipelineStatus: 'paused',
    artifactCount: 9,
    lastRunAt: minsAgo(34),
    repo: 'gitlab.com/acme/target-apps/meeting-assistant',
    environment: 'dev',
  },
  {
    id: 'rag-pdf-system',
    name: 'RAG PDF System',
    slug: 'rag-pdf-system',
    description: 'Document ingestion + retrieval-augmented Q&A over large PDF corpora with citations.',
    pipelineStatus: 'completed',
    artifactCount: 21,
    lastRunAt: minsAgo(180),
    repo: 'gitlab.com/acme/target-apps/rag-pdf-system',
    environment: 'prod',
  },
  {
    id: 'incident-triage-bot',
    name: 'Incident Triage Bot',
    slug: 'incident-triage-bot',
    description: 'On-call assistant that correlates alerts, proposes runbooks, and drafts incident timelines.',
    pipelineStatus: 'failed',
    artifactCount: 7,
    lastRunAt: minsAgo(95),
    repo: 'gitlab.com/acme/target-apps/incident-triage-bot',
    environment: 'dev',
  },
  {
    id: 'demo-api',
    name: 'Demo API',
    slug: 'demo-api',
    description: 'Reference FastAPI service used to validate the platform end-to-end pipeline.',
    pipelineStatus: 'queued',
    artifactCount: 4,
    lastRunAt: daysAgo(3),
    repo: 'gitlab.com/acme/target-apps/demo-api',
    environment: 'dev',
  },
  {
    id: 'customer-feedback-hub',
    name: 'Customer Feedback Hub',
    slug: 'customer-feedback-hub',
    description: 'Aggregates product feedback from multiple channels with sentiment tagging and theme clustering.',
    pipelineStatus: 'running',
    artifactCount: 6,
    lastRunAt: minsAgo(7),
    repo: 'gitlab.com/acme/target-apps/customer-feedback-hub',
    environment: 'dev',
  },
  {
    id: 'meeting-action-tracker',
    name: 'Meeting Action Tracker',
    slug: 'meeting-action-tracker',
    description: 'Extracts and tracks action items from meeting notes, with owner assignment and due-date reminders.',
    pipelineStatus: 'completed',
    artifactCount: 11,
    lastRunAt: minsAgo(52),
    repo: 'gitlab.com/acme/target-apps/meeting-action-tracker',
    environment: 'dev',
  },
];

export const mockPipelines: PipelineDefinition[] = [
  {
    id: 'standard-sdlc',
    name: 'Standard SDLC',
    description: 'Full end-to-end delivery pipeline from requirements to deploy with two HITL gates.',
    phases: [
      { phase: 'requirements', agent: 'product-agent', hitl: true },
      { phase: 'architecture', agent: 'architect-agent', hitl: false },
      { phase: 'data', agent: 'database-agent', hitl: false },
      { phase: 'implementation', agent: 'developer-agent', hitl: false },
      { phase: 'qa', agent: 'qa-agent', hitl: false },
      { phase: 'security', agent: 'security-agent', hitl: true },
      { phase: 'deploy', agent: 'devops-agent', hitl: false },
    ],
  },
  {
    id: 'hotfix',
    name: 'Hotfix',
    description: 'Expedited path for urgent fixes: implementation, QA, and gated deploy only.',
    phases: [
      { phase: 'implementation', agent: 'developer-agent', hitl: false },
      { phase: 'qa', agent: 'qa-agent', hitl: false },
      { phase: 'security', agent: 'security-agent', hitl: true },
      { phase: 'deploy', agent: 'devops-agent', hitl: false },
    ],
  },
  {
    id: 'research-spike',
    name: 'Research Spike',
    description: 'Discovery pipeline that crawls references and produces a PRD + architecture draft.',
    phases: [
      { phase: 'requirements', agent: 'product-agent', hitl: true },
      { phase: 'architecture', agent: 'architect-agent', hitl: false },
    ],
  },
];
