'use client';

import { create } from 'zustand';
import type { Environment, RunStatus } from '@/src/types';

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebar: (collapsed: boolean) => void;

  currentProjectId: string;
  setCurrentProject: (id: string) => void;

  /** Runs page only — null means show all projects. */
  runsProjectId: string | null;
  setRunsProject: (id: string | null) => void;

  /** Tokens page only — null = all-projects overview. */
  tokensProjectId: string | null;
  setTokensProjectId: (id: string | null) => void;

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

  environment: 'dev',
  setEnvironment: (env) => set({ environment: env }),

  runStatusFilter: 'all',
  setRunStatusFilter: (status) => set({ runStatusFilter: status }),

  selectedRunId: null,
  setSelectedRun: (id) => set({ selectedRunId: id }),

  globalSearch: '',
  setGlobalSearch: (q) => set({ globalSearch: q }),
}));
