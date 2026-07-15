'use client';

import { create } from 'zustand';
import type { Environment, RunStatus } from '@/src/types';

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebar: (collapsed: boolean) => void;

  currentProjectId: string;
  setCurrentProject: (id: string) => void;

  /** Runs page only - null means show all projects. */
  runsProjectId: string | null;
  setRunsProject: (id: string | null) => void;

  /** Tokens page only - null = all-projects overview. */
  tokensProjectId: string | null;
  setTokensProjectId: (id: string | null) => void;

  /** Logs page only - null = all projects. */
  logsProjectId: string | null;
  setLogsProjectId: (id: string | null) => void;

  /** Artifacts page only - null = all projects (default). */
  artifactsProjectId: string | null;
  setArtifactsProjectId: (id: string | null) => void;

  /** Context page only - null = all projects (default). */
  contextProjectId: string | null;
  setContextProjectId: (id: string | null) => void;

  /** HITL checkpoints page - null = all projects (default). */
  checkpointsProjectId: string | null;
  setCheckpointsProjectId: (id: string | null) => void;

  environment: Environment;
  setEnvironment: (env: Environment) => void;

  runStatusFilter: RunStatus | 'all';
  setRunStatusFilter: (status: RunStatus | 'all') => void;

  selectedRunId: string | null;
  setSelectedRun: (id: string | null) => void;

  globalSearch: string;
  setGlobalSearch: (q: string) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebar: (collapsed) => set({ sidebarCollapsed: collapsed }),

  currentProjectId: 'finops-web-app',
  setCurrentProject: (id) => set({ currentProjectId: id }),

  runsProjectId: null,
  setRunsProject: (id) => set({ runsProjectId: id }),

  tokensProjectId: null,
  setTokensProjectId: (id) => set({ tokensProjectId: id }),

  logsProjectId: null,
  setLogsProjectId: (id) => set({ logsProjectId: id }),

  artifactsProjectId: null,
  setArtifactsProjectId: (id) => set({ artifactsProjectId: id }),

  contextProjectId: null,
  setContextProjectId: (id) => set({ contextProjectId: id }),

  checkpointsProjectId: null,
  setCheckpointsProjectId: (id) => set({ checkpointsProjectId: id }),

  environment: 'dev',
  setEnvironment: (env) => set({ environment: env }),

  runStatusFilter: 'all',
  setRunStatusFilter: (status) => set({ runStatusFilter: status }),

  selectedRunId: null,
  setSelectedRun: (id) => set({ selectedRunId: id }),

  globalSearch: '',
  setGlobalSearch: (q) => set({ globalSearch: q }),
}));
