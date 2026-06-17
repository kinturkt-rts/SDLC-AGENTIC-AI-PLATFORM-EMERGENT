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
  artifacts: ['artifacts'] as const,
  checkpoints: ['checkpoints'] as const,
  mcp: ['mcp'] as const,
  context: ['context'] as const,
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
export const useArtifacts = () => useQuery({ queryKey: queryKeys.artifacts, queryFn: api.getArtifacts });
export const useCheckpoints = () =>
  useQuery({ queryKey: queryKeys.checkpoints, queryFn: api.getCheckpoints });
export const useMcpServers = () => useQuery({ queryKey: queryKeys.mcp, queryFn: api.getMcpServers });
export const useContextItems = () => useQuery({ queryKey: queryKeys.context, queryFn: api.getContextItems });
export const useLogs = () => useQuery({ queryKey: queryKeys.logs, queryFn: api.getLogs });
export const useDashboardSummary = () =>
  useQuery({ queryKey: queryKeys.dashboard, queryFn: api.getDashboardSummary });
