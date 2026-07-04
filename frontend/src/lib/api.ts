// Service layer for the control plane UI.
//
// When NEXT_PUBLIC_API_BASE_URL is unset, reads live monorepo state via Next.js
// routes under /api/v1/* (agents/pipeline/, target-apps/, docs/, a2a/).
// When set, calls the external platform REST API at that base URL.
//
// The control plane NEVER executes agents. It only reads platform state.

import { mockAgentMessages } from '@/src/mocks';
import type { ActivityFeedItem } from '@/src/lib/run-events';
import type { PlatformSettings } from '@/src/lib/platform-settings';
import type { PipelineTelemetrySummary, TelemetryOverviewRow } from '@/src/lib/pipeline-telemetry';
import type {
  Agent,
  Project,
  PipelineDefinition,
  PipelineRun,
  Artifact,
  HITLCheckpoint,
  McpServer,
  ContextItem,
  PipelineContext,
  LogEntry,
  DashboardSummary,
  RunStatus,
  AgentMessage,
  RunEvent,
  McpConfig,
  McpServerConfig,
  RunHandoffs,
} from '@/src/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
export const USING_MOCKS = !API_BASE_URL;
/** Local mode reads the monorepo via /api/v1 (not inline Emergent fixtures). */
export const USING_REPO_DATA = USING_MOCKS;

async function httpGet<T>(path: string): Promise<T> {
  const base = API_BASE_URL || '';
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export const api = {
  async getAgents(): Promise<Agent[]> {
    const data = await httpGet<{ agents: Agent[] }>('/api/v1/agents');
    return data.agents;
  },
  async getAgent(id: string): Promise<Agent | undefined> {
    try {
      return await httpGet<Agent>(`/api/v1/agents/${encodeURIComponent(id)}`);
    } catch {
      return undefined;
    }
  },
  async getProjects(): Promise<Project[]> {
    const data = await httpGet<{ projects: Project[] }>('/api/v1/projects');
    return data.projects;
  },
  async getProject(id: string): Promise<Project | undefined> {
    try {
      return await httpGet<Project>(`/api/v1/projects/${encodeURIComponent(id)}`);
    } catch {
      return undefined;
    }
  },
  async getPipelines(): Promise<PipelineDefinition[]> {
    const data = await httpGet<{ pipelines: PipelineDefinition[] }>('/api/v1/pipelines');
    return data.pipelines;
  },
  async getRuns(): Promise<PipelineRun[]> {
    const data = await httpGet<{ runs: PipelineRun[] }>('/api/v1/runs');
    return data.runs;
  },
  async getRun(id: string): Promise<PipelineRun | undefined> {
    try {
      return await httpGet<PipelineRun>(`/api/v1/runs/${encodeURIComponent(id)}`);
    } catch {
      return undefined;
    }
  },
  async getRunLogs(runId: string): Promise<LogEntry[]> {
    const data = await httpGet<{ logs: LogEntry[] }>(
      `/api/v1/runs/${encodeURIComponent(runId)}/logs`,
    );
    return data.logs;
  },
  async getRunEvents(runId: string): Promise<RunEvent[]> {
    const data = await httpGet<{ events: RunEvent[] }>(
      `/api/v1/runs/${encodeURIComponent(runId)}/events`,
    );
    return data.events;
  },
  async getRunHandoffs(runId: string): Promise<RunHandoffs | undefined> {
    try {
      return await httpGet<RunHandoffs>(`/api/v1/runs/${encodeURIComponent(runId)}/handoffs`);
    } catch {
      return undefined;
    }
  },
  async getRecentActivity(): Promise<ActivityFeedItem[]> {
    const data = await httpGet<{ activity: ActivityFeedItem[] }>('/api/v1/activity');
    return data.activity;
  },
  async getAgentMessages(correlationId?: string): Promise<AgentMessage[]> {
    const all = mockAgentMessages;
    return correlationId ? all.filter((m) => m.correlationId === correlationId) : all;
  },
  async controlRun(runId: string, action: 'pause' | 'resume' | 'cancel'): Promise<{ id: string; status: RunStatus }> {
    const status: RunStatus = action === 'pause' ? 'paused' : action === 'resume' ? 'running' : 'cancelled';
    return { id: runId, status };
  },
  async getArtifacts(): Promise<Artifact[]> {
    const data = await httpGet<{ artifacts: Artifact[] }>('/api/v1/artifacts');
    return data.artifacts;
  },
  async getCheckpoints(): Promise<HITLCheckpoint[]> {
    const data = await httpGet<{ checkpoints: HITLCheckpoint[] }>('/api/v1/checkpoints');
    return data.checkpoints;
  },
  async getMcpServers(): Promise<McpServer[]> {
    const data = await httpGet<{ servers: McpServer[] }>('/api/v1/mcp-servers');
    return data.servers;
  },
  async getMcpConfig(): Promise<McpConfig> {
    const r = await fetch('/api/mcp', { cache: 'no-store' });
    if (!r.ok) throw new Error('Failed to load mcp.json');
    return r.json();
  },
  async saveMcpServer(name: string, config: McpServerConfig): Promise<McpConfig> {
    const r = await fetch('/api/mcp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, config }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(Array.isArray(data.errors) ? data.errors.join(' ') : data.error || 'Save failed');
    return { mcpServers: data.mcpServers };
  },
  async deleteMcpServer(name: string): Promise<void> {
    const r = await fetch(`/api/mcp/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.error || 'Delete failed');
    }
  },
  async getContextItems(projectSlug?: string): Promise<ContextItem[]> {
    const qs = projectSlug ? `?projectSlug=${encodeURIComponent(projectSlug)}` : '';
    const data = await httpGet<{ items: ContextItem[] }>(`/api/v1/context${qs}`);
    return data.items;
  },
  async getPipelineContext(projectSlug: string): Promise<PipelineContext | null> {
    try {
      return await httpGet<PipelineContext>(`/api/v1/context/${encodeURIComponent(projectSlug)}`);
    } catch {
      return null;
    }
  },
  async getLogs(options?: {
    runId?: string;
    agent?: string;
    minutes?: number;
    source?: 'local' | 'cloudwatch';
    limit?: number;
  }): Promise<LogEntry[]> {
    const params = new URLSearchParams();
    if (options?.runId) params.set('runId', options.runId);
    if (options?.agent) params.set('agent', options.agent);
    if (options?.minutes) params.set('minutes', String(options.minutes));
    if (options?.source) params.set('source', options.source);
    if (options?.limit) params.set('limit', String(options.limit));
    const qs = params.toString();
    const data = await httpGet<{ logs: LogEntry[] }>(`/api/v1/logs${qs ? `?${qs}` : ''}`);
    return data.logs;
  },
  async getDashboardSummary(): Promise<DashboardSummary> {
    return httpGet<DashboardSummary>('/api/v1/dashboard');
  },
  async getPlatformSettings(): Promise<PlatformSettings> {
    return httpGet<PlatformSettings>('/api/v1/settings');
  },
  async getPipelineTelemetry(projectId: string): Promise<PipelineTelemetrySummary> {
    return httpGet<PipelineTelemetrySummary>(
      `/api/v1/telemetry?project=${encodeURIComponent(projectId)}`,
    );
  },
  async getTelemetryOverview(): Promise<TelemetryOverviewRow[]> {
    const data = await httpGet<{ projects: TelemetryOverviewRow[] }>('/api/v1/telemetry/overview');
    return data.projects;
  },
};
