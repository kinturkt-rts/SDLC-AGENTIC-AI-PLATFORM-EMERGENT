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
  runHandoffs: (id: string) => ['runs', id, 'handoffs'] as const,
  messages: (correlationId?: string) => ['messages', correlationId ?? 'all'] as const,
  artifacts: ['artifacts'] as const,
  checkpoints: ['checkpoints'] as const,
  mcp: ['mcp'] as const,
  mcpConfig: ['mcpConfig'] as const,
  context: (projectSlug?: string) => ['context', projectSlug ?? 'all'] as const,
  pipelineContext: (projectSlug: string) => ['pipelineContext', projectSlug] as const,
  logs: ['logs'] as const,
  dashboard: ['dashboard'] as const,
  activity: ['activity'] as const,
  settings: ['settings'] as const,
  telemetry: (projectId: string) => ['telemetry', projectId] as const,
  telemetryOverview: ['telemetryOverview'] as const,
};

export const useAgents = () =>
  useQuery({
    queryKey: queryKeys.agents,
    queryFn: api.getAgents,
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
export const useAgent = (id: string) =>
  useQuery({ queryKey: queryKeys.agent(id), queryFn: () => api.getAgent(id), enabled: !!id });
export const useProjects = () =>
  useQuery({
    queryKey: queryKeys.projects,
    queryFn: api.getProjects,
    staleTime: 10_000,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });
export const useProject = (id: string) =>
  useQuery({
    queryKey: queryKeys.project(id),
    queryFn: () => api.getProject(id),
    enabled: !!id,
    staleTime: 10_000,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });
export const usePipelines = () => useQuery({ queryKey: queryKeys.pipelines, queryFn: api.getPipelines });
export const useRuns = () =>
  useQuery({
    queryKey: queryKeys.runs,
    queryFn: api.getRuns,
    staleTime: 10_000,
    refetchInterval: (query) => {
      const runs = query.state.data;
      if (runs?.some((r) => r.status === 'running' || r.status === 'paused')) return 8_000;
      return 20_000;
    },
    refetchOnWindowFocus: true,
  });
export const useRun = (id: string) =>
  useQuery({
    queryKey: queryKeys.run(id),
    queryFn: () => api.getRun(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'running' || status === 'paused' ? 4000 : false;
    },
  });
export const useRunLogs = (id: string, live = false) =>
  useQuery({
    queryKey: queryKeys.runLogs(id),
    queryFn: () => api.getRunLogs(id),
    enabled: !!id,
    refetchInterval: live ? 8000 : false,
  });
export const useRunEvents = (id: string, live = false) =>
  useQuery({
    queryKey: queryKeys.runEvents(id),
    queryFn: () => api.getRunEvents(id),
    enabled: !!id,
    refetchInterval: live ? 4000 : false,
  });
export const useRunHandoffs = (id: string, live = false) =>
  useQuery({
    queryKey: queryKeys.runHandoffs(id),
    queryFn: () => api.getRunHandoffs(id),
    enabled: !!id,
    refetchInterval: live ? 4000 : false,
  });
export const useAgentMessages = (correlationId?: string, live = false) =>
  useQuery({
    queryKey: queryKeys.messages(correlationId),
    queryFn: () => api.getAgentMessages(correlationId),
    staleTime: 10_000,
    refetchInterval: live ? 8_000 : false,
  });
export const useArtifacts = (poll = false) =>
  useQuery({
    queryKey: queryKeys.artifacts,
    queryFn: api.getArtifacts,
    staleTime: 120_000,
    refetchInterval: poll ? 30_000 : false,
  });
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
  limit?: number;
};

export const useLogs = (filters: LogsFilter, live = false) =>
  useQuery({
    queryKey: [...queryKeys.logs, filters],
    queryFn: () => api.getLogs(filters),
    // Live views (All runs / running run): poll CloudWatch every 8s.
    // Finished single-run views: still refresh occasionally so late-arriving lines appear.
    staleTime: live ? 0 : 10_000,
    refetchInterval: live ? 8_000 : 30_000,
    refetchOnWindowFocus: true,
  });
export const useDashboardSummary = () =>
  useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: api.getDashboardSummary,
    staleTime: 120_000,
  });

export const useRecentActivity = (poll = true) =>
  useQuery({
    queryKey: queryKeys.activity,
    queryFn: () => api.getRecentActivity(),
    staleTime: 8_000,
    refetchInterval: poll ? 10_000 : false,
  });

export const usePlatformSettings = () =>
  useQuery({ queryKey: queryKeys.settings, queryFn: () => api.getPlatformSettings() });

export const usePipelineTelemetry = (projectId: string | null, poll = false) =>
  useQuery({
    queryKey: queryKeys.telemetry(projectId ?? ''),
    queryFn: () => api.getPipelineTelemetry(projectId!),
    enabled: Boolean(projectId),
    staleTime: 15_000,
    refetchInterval: poll ? 15_000 : false,
  });

export const useTelemetryOverview = () =>
  useQuery({
    queryKey: queryKeys.telemetryOverview,
    queryFn: () => api.getTelemetryOverview(),
    staleTime: 30_000,
  });
