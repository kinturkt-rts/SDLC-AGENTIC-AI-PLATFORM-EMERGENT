// Mock API service layer.
//
// Every function here returns a Promise, mirroring a future REST API at
// NEXT_PUBLIC_API_BASE_URL. When that env var is set, swap the mock branch for a
// real fetch() — the call sites (TanStack Query hooks) never change.
//
// The control plane NEVER executes agents. It only reads platform state.

import {
  mockAgents,
  mockProjects,
  mockPipelines,
  mockRuns,
  mockArtifacts,
  mockCheckpoints,
  mockMcpServers,
  mockContextItems,
  mockLogs,
} from '@/src/mocks';
import type {
  Agent,
  Project,
  PipelineDefinition,
  PipelineRun,
  Artifact,
  HITLCheckpoint,
  McpServer,
  ContextItem,
  LogEntry,
  DashboardSummary,
  RunStatus,
} from '@/src/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
export const USING_MOCKS = !API_BASE_URL;

function delay<T>(value: T, ms = 250): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

// Placeholder for the real implementation once the platform API exists.
// async function httpGet<T>(path: string): Promise<T> {
//   const res = await fetch(`${API_BASE_URL}${path}`, { headers: { Accept: 'application/json' } });
//   if (!res.ok) throw new Error(`API ${path} -> ${res.status}`);
//   return (await res.json()) as T;
// }

export const api = {
  async getAgents(): Promise<Agent[]> {
    return delay(mockAgents);
  },
  async getAgent(id: string): Promise<Agent | undefined> {
    return delay(mockAgents.find((a) => a.id === id));
  },
  async getProjects(): Promise<Project[]> {
    return delay(mockProjects);
  },
  async getProject(id: string): Promise<Project | undefined> {
    return delay(mockProjects.find((p) => p.id === id));
  },
  async getPipelines(): Promise<PipelineDefinition[]> {
    return delay(mockPipelines);
  },
  async getRuns(): Promise<PipelineRun[]> {
    return delay(mockRuns);
  },
  async getRun(id: string): Promise<PipelineRun | undefined> {
    return delay(mockRuns.find((r) => r.id === id));
  },
  // Run-scoped event stream. Structured as discrete LogEntry events so this can be
  // swapped for an SSE/WebSocket subscription (GET /runs/:id/events) without UI changes.
  async getRunLogs(runId: string): Promise<LogEntry[]> {
    return delay(mockLogs.filter((l) => l.runId === runId));
  },
  // Control-plane action against a run. Mock-only: maps the intent to a new status.
  // The real platform exposes POST /runs/:id/{pause|resume|cancel}; this NEVER runs agents.
  async controlRun(runId: string, action: 'pause' | 'resume' | 'cancel'): Promise<{ id: string; status: RunStatus }> {
    const status: RunStatus = action === 'pause' ? 'paused' : action === 'resume' ? 'running' : 'cancelled';
    return delay({ id: runId, status }, 350);
  },
  async getArtifacts(): Promise<Artifact[]> {
    return delay(mockArtifacts);
  },
  async getCheckpoints(): Promise<HITLCheckpoint[]> {
    return delay(mockCheckpoints);
  },
  async getMcpServers(): Promise<McpServer[]> {
    return delay(mockMcpServers);
  },
  async getContextItems(): Promise<ContextItem[]> {
    return delay(mockContextItems);
  },
  async getLogs(): Promise<LogEntry[]> {
    return delay(mockLogs);
  },
  async getDashboardSummary(): Promise<DashboardSummary> {
    const activeRuns = mockRuns.filter((r) => r.status === 'running').length;
    const pendingApprovals = mockCheckpoints.filter((c) => c.status === 'pending').length;
    const agentsOnline = mockAgents.filter((a) => a.availability === 'online').length;
    const mcpHealthy = mockMcpServers.filter((m) => m.status === 'healthy').length;
    return delay({
      activeRuns,
      pendingApprovals,
      agentsOnline,
      agentsTotal: mockAgents.length,
      mcpHealthy,
      mcpTotal: mockMcpServers.length,
    });
  },
};
