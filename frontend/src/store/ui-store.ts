'use client';

import { create } from 'zustand';
import type { Environment, RunStatus } from '@/src/types';

const RECENTS_KEY = 'sdlc-recent-visits';

type Recents = { runs: string[]; projects: string[] };

function loadRecents(): Recents {
  if (typeof window === 'undefined') return { runs: [], projects: [] };
  try {
    const raw = window.localStorage.getItem(RECENTS_KEY);
    const p = raw ? JSON.parse(raw) : null;
    return {
      runs: Array.isArray(p?.runs) ? p.runs : [],
      projects: Array.isArray(p?.projects) ? p.projects : [],
    };
  } catch {
    return { runs: [], projects: [] };
  }
}

function saveRecents(r: Recents): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(RECENTS_KEY, JSON.stringify(r));
  } catch {
    /* ignore storage errors */
  }
}

function prependUnique(list: string[], id: string, cap = 6): string[] {
  return [id, ...list.filter((x) => x !== id)].slice(0, cap);
}

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

  /** Recently visited run / project ids (persisted). */
  recentRunIds: string[];
  recentProjectIds: string[];
  pushRecentRun: (id: string) => void;
  pushRecentProject: (id: string) => void;
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

  recentRunIds: loadRecents().runs,
  recentProjectIds: loadRecents().projects,
  pushRecentRun: (id) =>
    set((s) => {
      const runs = prependUnique(s.recentRunIds, id);
      saveRecents({ runs, projects: s.recentProjectIds });
      return { recentRunIds: runs };
    }),
  pushRecentProject: (id) =>
    set((s) => {
      const projects = prependUnique(s.recentProjectIds, id);
      saveRecents({ runs: s.recentRunIds, projects });
      return { recentProjectIds: projects };
    }),
}));
