import type { Artifact } from '@/src/types';
import { minsAgo } from './time';

export const FINOPS_PRD_PREVIEW = `# FinOps Web App — Product Requirements

## 1. Problem
Engineering and finance lack a shared, real-time view of cloud spend. Budgets are
tracked in spreadsheets; anomalies are discovered after invoices arrive.

## 2. Goals
- Unified cost dashboard across AWS / GCP / Azure
- Budget definitions with threshold alerts (50/80/100%)
- Chargeback / showback reports by team and service
- Anomaly detection on daily spend

## 3. User Stories
- As a **FinOps lead**, I can set a monthly budget per team so that overspend is flagged early.
- As an **engineer**, I can see my service's cost trend so that I can optimize resources.
- As a **finance analyst**, I can export a chargeback report so that costs are allocated correctly.

## 4. Acceptance Criteria
- Dashboard loads p95 < 1.5s with 90 days of data
- Alerts delivered within 5 minutes of threshold breach
- Reports exportable as CSV and PDF

## 5. Out of Scope (v1)
- Reserved-instance purchase recommendations
- Multi-currency normalization
`;

export const mockArtifacts: Artifact[] = [
  {
    id: 'art-prd-001',
    name: 'PRD.md',
    kind: 'prd',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    producedBy: 'product-agent',
    runId: 'run-8f2a91',
    path: 'target-apps/finops-web-app/docs/PRD.md',
    sizeKb: 12.4,
    createdAt: minsAgo(38),
    preview: FINOPS_PRD_PREVIEW,
  },
  {
    id: 'art-arch-001',
    name: 'architecture.md',
    kind: 'architecture',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    producedBy: 'architect-agent',
    runId: 'run-8f2a91',
    path: 'target-apps/finops-web-app/docs/architecture.md',
    sizeKb: 18.1,
    createdAt: minsAgo(31),
  },
  {
    id: 'art-diag-001',
    name: 'system-diagram.png',
    kind: 'diagram',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    producedBy: 'architect-agent',
    runId: 'run-8f2a91',
    path: 'target-apps/finops-web-app/docs/diagrams/system.png',
    sizeKb: 145.7,
    createdAt: minsAgo(31),
    imageUrl: '/diagrams/finops-web-app.png',
  },
  {
    id: 'art-mig-001',
    name: '0001_init_schema.sql',
    kind: 'migration',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    producedBy: 'database-agent',
    runId: 'run-8f2a91',
    path: 'target-apps/finops-web-app/migrations/0001_init_schema.sql',
    sizeKb: 6.8,
    createdAt: minsAgo(24),
    preview: 'CREATE TABLE budgets (\n  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n  team_id UUID NOT NULL,\n  amount_cents BIGINT NOT NULL,\n  period TEXT NOT NULL,\n  created_at TIMESTAMPTZ DEFAULT now()\n);',
  },
  {
    id: 'art-code-001',
    name: 'budgets_router.py',
    kind: 'code',
    projectId: 'finops-web-app',
    projectName: 'FinOps Web App',
    producedBy: 'developer-agent',
    runId: 'run-8f2a91',
    path: 'target-apps/finops-web-app/app/routers/budgets.py',
    sizeKb: 9.2,
    createdAt: minsAgo(8),
    preview: 'from fastapi import APIRouter, Depends\n\nrouter = APIRouter(prefix="/budgets", tags=["budgets"])\n\n@router.get("/")\nasync def list_budgets():\n    ...',
  },
  {
    id: 'art-test-001',
    name: 'test_budgets.py',
    kind: 'test',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    producedBy: 'qa-agent',
    runId: 'run-1a40be',
    path: 'target-apps/rag-pdf-system/tests/test_budgets.py',
    sizeKb: 5.1,
    createdAt: minsAgo(190),
  },
  {
    id: 'art-scan-001',
    name: 'security-scan.sarif',
    kind: 'scan',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    producedBy: 'security-agent',
    runId: 'run-1a40be',
    path: 'target-apps/rag-pdf-system/reports/security-scan.sarif',
    sizeKb: 33.5,
    createdAt: minsAgo(185),
  },
  {
    id: 'art-cicd-001',
    name: '.gitlab-ci.yml',
    kind: 'cicd',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    producedBy: 'devops-agent',
    runId: 'run-1a40be',
    path: 'target-apps/rag-pdf-system/.gitlab-ci.yml',
    sizeKb: 4.4,
    createdAt: minsAgo(182),
  },
  {
    id: 'art-diag-002',
    name: 'system-diagram.png',
    kind: 'diagram',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    producedBy: 'architect-agent',
    runId: 'run-1a40be',
    path: 'target-apps/rag-pdf-system/docs/diagrams/system.png',
    sizeKb: 96.6,
    createdAt: minsAgo(192),
    imageUrl: '/diagrams/rag-pdf-system.png',
  },
  {
    id: 'art-tf-001',
    name: 'main.tf',
    kind: 'cicd',
    projectId: 'rag-pdf-system',
    projectName: 'RAG PDF System',
    producedBy: 'devops-agent',
    runId: 'run-1a40be',
    path: 'target-apps/rag-pdf-system/infra/main.tf',
    sizeKb: 11.9,
    createdAt: minsAgo(181),
  },
  {
    id: 'art-prd-002',
    name: 'PRD.md',
    kind: 'prd',
    projectId: 'meeting-assistant',
    projectName: 'Meeting Assistant',
    producedBy: 'product-agent',
    runId: 'run-3c77d0',
    path: 'target-apps/meeting-assistant/docs/PRD.md',
    sizeKb: 10.7,
    createdAt: minsAgo(118),
  },
  {
    id: 'art-doc-001',
    name: 'adr-0003-event-bus.md',
    kind: 'doc',
    projectId: 'meeting-assistant',
    projectName: 'Meeting Assistant',
    producedBy: 'architect-agent',
    runId: 'run-3c77d0',
    path: 'target-apps/meeting-assistant/docs/adr/0003-event-bus.md',
    sizeKb: 3.3,
    createdAt: minsAgo(112),
  },
  {
    id: 'art-diag-003',
    name: 'system-diagram.png',
    kind: 'diagram',
    projectId: 'meeting-assistant',
    projectName: 'Meeting Assistant',
    producedBy: 'architect-agent',
    runId: 'run-3c77d0',
    path: 'target-apps/meeting-assistant/docs/diagrams/system.png',
    sizeKb: 118.9,
    createdAt: minsAgo(115),
    imageUrl: '/diagrams/meeting-assistant.png',
  },
  {
    id: 'art-mig-002',
    name: '0002_add_actions.sql',
    kind: 'migration',
    projectId: 'meeting-assistant',
    projectName: 'Meeting Assistant',
    producedBy: 'database-agent',
    runId: 'run-3c77d0',
    path: 'target-apps/meeting-assistant/migrations/0002_add_actions.sql',
    sizeKb: 2.9,
    createdAt: minsAgo(101),
  },
];
