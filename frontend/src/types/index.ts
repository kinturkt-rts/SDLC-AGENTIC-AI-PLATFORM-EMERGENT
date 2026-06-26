// Core domain types for the SDLC Agentic AI Platform control plane.

export type AgentName =
  | 'orchestrator-agent'
  | 'product-agent'
  | 'architect-agent'
  | 'web-crawler-agent'
  | 'database-agent'
  | 'developer-agent'
  | 'gitlab-agent'
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
  imageUrl?: string;
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
  projectSlug: string;
  projectName: string;
  key: string;
  scope: 'project' | 'run' | 'global';
  type: 'document' | 'memory' | 'decision' | 'reference';
  summary: string;
  updatedAt: string;
  tokens: number;
}

// Pipeline handoff context written by agents during a run (aligns with real handoff JSON).
export interface PipelineContext {
  targetApp: string;
  prdPath: string;
  designDocPath: string;
  diagramPaths: string[];
  productAgentOutput: string;
  architectSummary: string;
  dbOutputDir: string;
  preferredSqlPath: string;
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

// ---- Orchestration bus ----
export type AgentMessageType =
  | 'task.assign'
  | 'task.result'
  | 'task.error'
  | 'status.update'
  | 'hitl.request'
  | 'hitl.resolved';

export interface AgentMessage {
  id: string;
  type: AgentMessageType;
  from: AgentName;
  to: AgentName;
  correlationId: string; // groups a delegation thread
  runId: string;
  ts: string;
  summary: string;
}

// ---- Discriminated run event stream (SSE-ready) ----
interface RunEventBase {
  id: string;
  runId: string;
  ts: string;
}

export type RunEvent =
  | (RunEventBase & { kind: 'log'; level: LogEntry['level']; agent: AgentName; message: string })
  | (RunEventBase & { kind: 'phase.started'; phase: SdlcPhase; agent: AgentName })
  | (RunEventBase & { kind: 'phase.completed'; phase: SdlcPhase; agent: AgentName; durationSec: number })
  | (RunEventBase & { kind: 'step.failed'; phase: SdlcPhase; agent: AgentName; error: string })
  | (RunEventBase & { kind: 'hitl.requested'; phase: SdlcPhase; agent: AgentName; checkpointId: string; title: string })
  | (RunEventBase & { kind: 'artifact.created'; agent: AgentName; artifactName: string; artifactKind: ArtifactKind })
  | (RunEventBase & {
      kind: 'agent.message';
      from: AgentName;
      to: AgentName;
      messageType: AgentMessageType;
      summary: string;
    });

export type RunEventKind = RunEvent['kind'];

// ---- MCP (Cursor mcp.json format) ----
export interface McpServerConfig {
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  envFile?: string;
  disabled?: boolean;
  timeout?: number;
  type?: string;
  url?: string;
}

export interface McpConfig {
  mcpServers: Record<string, McpServerConfig>;
}

export interface McpValidationResult {
  valid: boolean;
  errors: string[];
}
