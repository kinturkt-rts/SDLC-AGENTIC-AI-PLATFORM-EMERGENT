'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from './api';

export const queryKeys = {
  agents: ['agents'] as const,
  agent: (id: string) => ['agents', id] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['projects', id] as const,
  pipelines: ['pipelines'] as const,
  runs: ['runs'] as const,
  run: (id: string) => ['runs', id] as const,
  runLogs: (id: string) => ['runs', id, 'logs'] as const,
  runEvents: (id: string) => ['runs', id, 'events'] as const,
  messages: (correlationId?: string) => ['messages', correlationId ?? 'all'] as const,
  artifacts: ['artifacts'] as const,
  checkpoints: ['checkpoints'] as const,
  mcp: ['mcp'] as const,
  mcpConfig: ['mcpConfig'] as const,
  context: (projectSlug?: string) => ['context', projectSlug ?? 'all'] as const,
  pipelineContext: (projectSlug: string) => ['pipelineContext', projectSlug] as const,
  logs: ['logs'] as const,
  dashboard: ['dashboard'] as const,
};

export const useAgents = () => useQuery({ queryKey: queryKeys.agents, queryFn: api.getAgents });
export const useAgent = (id: string) =>
  useQuery({ queryKey: queryKeys.agent(id), queryFn: () => api.getAgent(id), enabled: !!id });
export const useProjects = () => useQuery({ queryKey: queryKeys.projects, queryFn: api.getProjects });
export const useProject = (id: string) =>
  useQuery({ queryKey: queryKeys.project(id), queryFn: () => api.getProject(id), enabled: !!id });
export const usePipelines = () => useQuery({ queryKey: queryKeys.pipelines, queryFn: api.getPipelines });
export const useRuns = () => useQuery({ queryKey: queryKeys.runs, queryFn: api.getRuns });
export const useRun = (id: string) =>
  useQuery({ queryKey: queryKeys.run(id), queryFn: () => api.getRun(id), enabled: !!id });
export const useRunLogs = (id: string) =>
  useQuery({ queryKey: queryKeys.runLogs(id), queryFn: () => api.getRunLogs(id), enabled: !!id });
export const useRunEvents = (id: string) =>
  useQuery({ queryKey: queryKeys.runEvents(id), queryFn: () => api.getRunEvents(id), enabled: !!id });
export const useAgentMessages = (correlationId?: string) =>
  useQuery({ queryKey: queryKeys.messages(correlationId), queryFn: () => api.getAgentMessages(correlationId) });
export const useArtifacts = () => useQuery({ queryKey: queryKeys.artifacts, queryFn: api.getArtifacts });
export const useCheckpoints = () =>
  useQuery({ queryKey: queryKeys.checkpoints, queryFn: api.getCheckpoints });
export const useMcpServers = () => useQuery({ queryKey: queryKeys.mcp, queryFn: api.getMcpServers });
export const useMcpConfig = () => useQuery({ queryKey: queryKeys.mcpConfig, queryFn: api.getMcpConfig });
export const useContextItems = (projectSlug?: string) =>
  useQuery({ queryKey: queryKeys.context(projectSlug), queryFn: () => api.getContextItems(projectSlug) });
export const usePipelineContext = (projectSlug: string) =>
  useQuery({ queryKey: queryKeys.pipelineContext(projectSlug), queryFn: () => api.getPipelineContext(projectSlug), enabled: !!projectSlug });
export type LogsFilter = {
  runId?: string;
  agent?: string;
  minutes?: number;
};

export const useLogs = (filters?: LogsFilter) =>
  useQuery({
    queryKey: [...queryKeys.logs, filters ?? {}],
    queryFn: () => api.getLogs(filters),
    refetchInterval: filters?.minutes && filters.minutes <= 30 ? 5000 : 30_000,
  });
export const useDashboardSummary = () =>
  useQuery({ queryKey: queryKeys.dashboard, queryFn: api.getDashboardSummary });
