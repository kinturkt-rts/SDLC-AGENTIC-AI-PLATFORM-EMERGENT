// Core domain types for the SDLC Agentic AI Platform control plane.

export type AgentName =
  | 'orchestrator-agent'
  | 'product-agent'
  | 'architect-agent'
  | 'web-crawler-agent'
  | 'database-agent'
  | 'developer-agent'
  | 'qa-agent'
  | 'devops-agent'
  | 'security-agent';

export type RunStatus =
  | 'queued'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type StepStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'waiting_for_human'
  | 'skipped';

export type SdlcPhase =
  | 'requirements'
  | 'architecture'
  | 'data'
  | 'implementation'
  | 'qa'
  | 'security'
  | 'deploy';

export type AgentAvailability = 'online' | 'offline' | 'unknown';

export type ArtifactKind =
  | 'prd'
  | 'architecture'
  | 'migration'
  | 'code'
  | 'test'
  | 'scan'
  | 'cicd'
  | 'diagram'
  | 'doc';

export type McpServerName =
  | 'Atlassian'
  | 'GitLab'
  | 'Postgres'
  | 'MongoDB'
  | 'Firecrawl'
  | 'AWS Diagram'
  | 'Terraform';

export type McpHealth = 'healthy' | 'degraded' | 'down';

export type Environment = 'dev' | 'staging' | 'prod';

export interface Agent {
  id: string; // slug, equals name
  name: AgentName;
  displayName: string;
  role: string;
  skills: string[];
  mcpTools: string[];
  mcpServers: McpServerName[];
  port: number;
  availability: AgentAvailability;
  lastRunAt: string | null;
  phase: SdlcPhase | null;
}

export interface PipelineStep {
  id: string;
  phase: SdlcPhase;
  agent: AgentName;
  status: StepStatus;
  startedAt: string | null;
  finishedAt: string | null;
  durationSec: number | null;
}

export interface PipelineRun {
  id: string;
  projectId: string;
  projectName: string;
  pipeline: string;
  status: RunStatus;
  currentPhase: SdlcPhase | null;
  currentAgent: AgentName | null;
  startedAt: string;
  finishedAt: string | null;
  elapsedSec: number;
  triggeredBy: string;
  steps: PipelineStep[];
}

export interface Artifact {
  id: string;
  name: string;
  kind: ArtifactKind;
  projectId: string;
  projectName: string;
  producedBy: AgentName;
  runId: string;
  path: string;
  sizeKb: number;
  createdAt: string;
  preview?: string;
}

export interface HITLCheckpoint {
  id: string;
  runId: string;
  projectId: string;
  projectName: string;
  phase: SdlcPhase;
  agent: AgentName;
  title: string;
  description: string;
  requestedAt: string;
  status: 'pending' | 'approved' | 'rejected';
  approver?: string;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string;
  pipelineStatus: RunStatus;
  artifactCount: number;
  lastRunAt: string;
  repo: string;
  environment: Environment;
}

export interface PipelineDefinition {
  id: string;
  name: string;
  description: string;
  phases: { phase: SdlcPhase; agent: AgentName; hitl: boolean }[];
}

export interface McpServer {
  id: string;
  name: McpServerName;
  description: string;
  status: McpHealth;
  endpoint: string;
  tools: string[];
  latencyMs: number;
  usedByAgents: AgentName[];
}

export interface ContextItem {
  id: string;
  projectId: string;
  projectName: string;
  key: string;
  scope: 'project' | 'run' | 'global';
  type: 'document' | 'memory' | 'decision' | 'reference';
  summary: string;
  updatedAt: string;
  tokens: number;
}

export interface LogEntry {
  id: string;
  ts: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  agent: AgentName;
  runId: string;
  message: string;
}

export interface DashboardSummary {
  activeRuns: number;
  pendingApprovals: number;
  agentsOnline: number;
  agentsTotal: number;
  mcpHealthy: number;
  mcpTotal: number;
}
