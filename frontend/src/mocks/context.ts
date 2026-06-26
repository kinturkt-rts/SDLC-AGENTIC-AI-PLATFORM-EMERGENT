import type { ContextItem, PipelineContext } from '@/src/types';
import { minsAgo, daysAgo } from './time';

// Per-project context. When a single project is selected, only its rows are shown.
export const mockContextItems: ContextItem[] = [
  // finops-web-app
  { id: 'ctx-fin-1', projectId: 'finops-web-app', projectSlug: 'finops-web-app', projectName: 'FinOps Web App', key: 'prd.summary', scope: 'project', type: 'document', summary: 'Condensed PRD: budgeting, threshold alerts, chargeback, anomaly detection (v1).', updatedAt: minsAgo(38), tokens: 1840 },
  { id: 'ctx-fin-2', projectId: 'finops-web-app', projectSlug: 'finops-web-app', projectName: 'FinOps Web App', key: 'schema.budgets', scope: 'run', type: 'reference', summary: 'budgets / alerts / chargeback_reports tables with indexes.', updatedAt: minsAgo(24), tokens: 640 },
  { id: 'ctx-fin-3', projectId: 'finops-web-app', projectSlug: 'finops-web-app', projectName: 'FinOps Web App', key: 'design.decisions', scope: 'project', type: 'decision', summary: 'Defer multi-currency normalization to v2 (per HITL sign-off).', updatedAt: minsAgo(34), tokens: 120 },

  // rag-pdf-system
  { id: 'ctx-rag-1', projectId: 'rag-pdf-system', projectSlug: 'rag-pdf-system', projectName: 'RAG PDF System', key: 'prd.summary', scope: 'project', type: 'document', summary: 'Document ingestion + retrieval-augmented Q&A over large PDF corpora with citations.', updatedAt: minsAgo(210), tokens: 1520 },
  { id: 'ctx-rag-2', projectId: 'rag-pdf-system', projectSlug: 'rag-pdf-system', projectName: 'RAG PDF System', key: 'crawler.refs', scope: 'run', type: 'reference', summary: 'Crawled embedding-provider + vector-store API docs cited in architecture.', updatedAt: minsAgo(208), tokens: 3200 },
  { id: 'ctx-rag-3', projectId: 'rag-pdf-system', projectSlug: 'rag-pdf-system', projectName: 'RAG PDF System', key: 'schema.embeddings', scope: 'run', type: 'reference', summary: 'pgvector embeddings table (1536 dims) + ivfflat index strategy.', updatedAt: minsAgo(190), tokens: 540 },

  // customer-feedback-hub
  { id: 'ctx-cfh-1', projectId: 'customer-feedback-hub', projectSlug: 'customer-feedback-hub', projectName: 'Customer Feedback Hub', key: 'prd.summary', scope: 'project', type: 'document', summary: 'Multi-channel feedback aggregation with sentiment tagging and theme clustering.', updatedAt: minsAgo(7), tokens: 1280 },
  { id: 'ctx-cfh-2', projectId: 'customer-feedback-hub', projectSlug: 'customer-feedback-hub', projectName: 'Customer Feedback Hub', key: 'sentiment.model.choice', scope: 'project', type: 'decision', summary: 'Use hosted classification endpoint; fall back to lexicon scoring offline.', updatedAt: minsAgo(6), tokens: 210 },
  { id: 'ctx-cfh-3', projectId: 'customer-feedback-hub', projectSlug: 'customer-feedback-hub', projectName: 'Customer Feedback Hub', key: 'schema.feedback', scope: 'run', type: 'reference', summary: 'feedback / channels / themes tables with sentiment + cluster_id columns.', updatedAt: minsAgo(5), tokens: 480 },

  // meeting-action-tracker
  { id: 'ctx-mat-1', projectId: 'meeting-action-tracker', projectSlug: 'meeting-action-tracker', projectName: 'Meeting Action Tracker', key: 'prd.summary', scope: 'project', type: 'document', summary: 'Extract action items from notes; assign owners and due dates; send reminders.', updatedAt: minsAgo(52), tokens: 1120 },
  { id: 'ctx-mat-2', projectId: 'meeting-action-tracker', projectSlug: 'meeting-action-tracker', projectName: 'Meeting Action Tracker', key: 'nlp.extraction.rules', scope: 'run', type: 'reference', summary: 'Heuristics + prompt for action-item extraction (owner, verb, deadline).', updatedAt: minsAgo(50), tokens: 760 },
  { id: 'ctx-mat-3', projectId: 'meeting-action-tracker', projectSlug: 'meeting-action-tracker', projectName: 'Meeting Action Tracker', key: 'schema.actions', scope: 'run', type: 'reference', summary: 'actions / owners / reminders tables with status + due_at.', updatedAt: minsAgo(49), tokens: 520 },
  { id: 'ctx-mat-4', projectId: 'meeting-action-tracker', projectSlug: 'meeting-action-tracker', projectName: 'Meeting Action Tracker', key: 'memory.reviewer-notes', scope: 'project', type: 'memory', summary: 'Reviewer guidance on false-positive action items and owner inference.', updatedAt: minsAgo(48), tokens: 340 },

  // meeting-assistant
  { id: 'ctx-ma-1', projectId: 'meeting-assistant', projectSlug: 'meeting-assistant', projectName: 'Meeting Assistant', key: 'prd.summary', scope: 'project', type: 'document', summary: 'Real-time transcription, action-item extraction, and summary delivery.', updatedAt: minsAgo(118), tokens: 1080 },
  { id: 'ctx-ma-2', projectId: 'meeting-assistant', projectSlug: 'meeting-assistant', projectName: 'Meeting Assistant', key: 'memory.user-feedback', scope: 'project', type: 'memory', summary: 'Accumulated notes on transcription accuracy expectations and latency budget.', updatedAt: minsAgo(101), tokens: 980 },
  { id: 'ctx-ma-3', projectId: 'meeting-assistant', projectSlug: 'meeting-assistant', projectName: 'Meeting Assistant', key: 'adr.event-bus', scope: 'project', type: 'decision', summary: 'ADR-0003: choose event bus for action dispatch (decoupled consumers).', updatedAt: minsAgo(112), tokens: 260 },
];

// Pipeline handoff context per project (agent-written JSON). Empty for projects without a run.
export const mockPipelineContext: Record<string, PipelineContext> = {
  'finops-web-app': {
    targetApp: 'finops-web-app',
    prdPath: 'target-apps/finops-web-app/docs/PRD.md',
    designDocPath: 'target-apps/finops-web-app/docs/architecture.md',
    diagramPaths: ['target-apps/finops-web-app/docs/diagrams/system.png'],
    productAgentOutput: 'PRD approved; multi-currency deferred to v2.',
    architectSummary: 'Modular monolith: API + worker + Postgres; event-driven alerts.',
    dbOutputDir: 'target-apps/finops-web-app/migrations',
    preferredSqlPath: 'target-apps/finops-web-app/migrations/0001_init_schema.sql',
  },
  'rag-pdf-system': {
    targetApp: 'rag-pdf-system',
    prdPath: 'target-apps/rag-pdf-system/docs/PRD.md',
    designDocPath: 'target-apps/rag-pdf-system/docs/architecture.md',
    diagramPaths: ['target-apps/rag-pdf-system/docs/diagrams/ingestion.png', 'target-apps/rag-pdf-system/docs/diagrams/retrieval.png'],
    productAgentOutput: 'PRD finalized; citations are a hard requirement.',
    architectSummary: 'Ingestion pipeline + pgvector store + RAG query service with reranking.',
    dbOutputDir: 'target-apps/rag-pdf-system/migrations',
    preferredSqlPath: 'target-apps/rag-pdf-system/migrations/0003_embeddings.sql',
  },
  'customer-feedback-hub': {
    targetApp: 'customer-feedback-hub',
    prdPath: 'target-apps/customer-feedback-hub/docs/PRD.md',
    designDocPath: 'target-apps/customer-feedback-hub/docs/architecture.md',
    diagramPaths: ['target-apps/customer-feedback-hub/docs/diagrams/ingest.png'],
    productAgentOutput: 'PRD drafted; sentiment + theme clustering in scope for v1.',
    architectSummary: 'Channel collectors -> queue -> classifier -> aggregation API.',
    dbOutputDir: 'target-apps/customer-feedback-hub/migrations',
    preferredSqlPath: 'target-apps/customer-feedback-hub/migrations/0001_feedback.sql',
  },
  'meeting-action-tracker': {
    targetApp: 'meeting-action-tracker',
    prdPath: 'target-apps/meeting-action-tracker/docs/PRD.md',
    designDocPath: 'target-apps/meeting-action-tracker/docs/architecture.md',
    diagramPaths: ['target-apps/meeting-action-tracker/docs/diagrams/flow.png'],
    productAgentOutput: 'PRD approved; reminders via scheduled jobs.',
    architectSummary: 'Note ingest -> extraction service -> actions store -> reminder scheduler.',
    dbOutputDir: 'target-apps/meeting-action-tracker/migrations',
    preferredSqlPath: 'target-apps/meeting-action-tracker/migrations/0002_actions.sql',
  },
  'meeting-assistant': {
    targetApp: 'meeting-assistant',
    prdPath: 'target-apps/meeting-assistant/docs/PRD.md',
    designDocPath: 'target-apps/meeting-assistant/docs/architecture.md',
    diagramPaths: ['target-apps/meeting-assistant/docs/diagrams/system.png'],
    productAgentOutput: 'PRD drafted; transcription accuracy SLO defined.',
    architectSummary: 'Streaming transcription + event bus + summary service.',
    dbOutputDir: 'target-apps/meeting-assistant/migrations',
    preferredSqlPath: 'target-apps/meeting-assistant/migrations/0002_add_actions.sql',
  },
};

void daysAgo;
