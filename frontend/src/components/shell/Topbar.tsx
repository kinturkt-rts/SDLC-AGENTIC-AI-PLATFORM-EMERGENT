'use client';

import * as React from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ThemeToggle } from '@/src/components/common/ThemeToggle';
import { shouldShowProjectFilter } from '@/src/lib/project-filter';
import { useUiStore } from '@/src/store/ui-store';
import { useProjects, useRuns } from '@/src/lib/queries';

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const isTokensPage = pathname === '/tokens' || pathname.startsWith('/tokens/');
  const isRunsPage = pathname === '/runs' || pathname.startsWith('/runs/');
  const isLogsPage = pathname === '/logs' || pathname.startsWith('/logs/');
  const showProjectFilter = shouldShowProjectFilter(pathname);
  const { data: projects } = useProjects();
  const { data: runs } = useRuns();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);
  const runsProjectId = useUiStore((s) => s.runsProjectId);
  const setRunsProject = useUiStore((s) => s.setRunsProject);
  const tokensProjectId = useUiStore((s) => s.tokensProjectId);
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);
  const logsProjectId = useUiStore((s) => s.logsProjectId);
  const setLogsProjectId = useUiStore((s) => s.setLogsProjectId);

  const runProjectIds = new Set((runs ?? []).map((r) => r.projectId));
  const activeRunId = pathname?.startsWith('/runs/') ? pathname.split('/')[2] : null;
  const activeRun = activeRunId ? (runs ?? []).find((r) => r.id === activeRunId) : undefined;

  const projectOptions = isTokensPage || isRunsPage || isLogsPage
    ? (projects ?? []).filter((p) => runProjectIds.has(p.id))
    : (projects ?? []);

  React.useEffect(() => {
    if (isTokensPage || isRunsPage || isLogsPage) return;
    if (!projects?.length) return;
    if (!projects.some((p) => p.id === currentProjectId)) {
      setCurrentProject(projects[0].id);
    }
  }, [isTokensPage, isRunsPage, isLogsPage, projects, currentProjectId, setCurrentProject]);

  const selectedId = isTokensPage
    ? tokensProjectId
    : isRunsPage
      ? activeRun?.projectId ?? runsProjectId
      : isLogsPage
        ? logsProjectId
        : currentProjectId;

  const onProjectChange = (id: string) => {
    if (isTokensPage) {
      setTokensProjectId(id === '__all__' ? null : id);
      return;
    }

    if (isLogsPage) {
      setLogsProjectId(id === '__all__' ? null : id);
      return;
    }

    if (isRunsPage) {
      if (id === '__all__') {
        setRunsProject(null);
        router.push('/runs');
        return;
      }
      setRunsProject(id);
      const latestRun = (runs ?? []).find((r) => r.projectId === id);
      if (pathname?.startsWith('/runs/') && latestRun) {
        router.push(`/runs/${latestRun.id}`);
      }
      return;
    }

    setCurrentProject(id);
  };

  const currentProjectName = selectedId
    ? projectOptions.find((p) => p.id === selectedId)?.name ?? 'Select project'
    : isRunsPage || isTokensPage || isLogsPage
      ? 'All projects'
      : 'Select project';

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl">
      {showProjectFilter ? (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Project</span>
          <Select
            value={selectedId ?? '__all__'}
            onValueChange={onProjectChange}
          >
            <SelectTrigger className="h-9 w-auto min-w-[9rem] max-w-[12rem] shrink-0 border-white/[0.08] bg-white/[0.02] px-2.5 text-sm transition-colors hover:border-white/[0.14] [&>span]:truncate">
              <SelectValue placeholder="Select project">{currentProjectName}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {(isRunsPage || isTokensPage || isLogsPage) ? (
                <SelectItem value="__all__">All projects</SelectItem>
              ) : null}
              {projectOptions.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {isTokensPage && selectedId ? (
            <button
              type="button"
              onClick={() => setTokensProjectId(null)}
              className="text-xs text-muted-foreground hover:text-teal-400"
            >
              All projects
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
      </div>
    </header>
  );
}
