'use client';

import * as React from 'react';
import { usePathname } from 'next/navigation';
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
  const isTokensPage = pathname === '/tokens' || pathname.startsWith('/tokens/');
  const showProjectFilter = shouldShowProjectFilter(pathname);
  const { data: projects } = useProjects();
  const { data: runs } = useRuns();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);
  const tokensProjectId = useUiStore((s) => s.tokensProjectId);
  const setTokensProjectId = useUiStore((s) => s.setTokensProjectId);

  const runProjectIds = new Set((runs ?? []).map((r) => r.projectId));

  const projectOptions = isTokensPage
    ? (projects ?? []).filter((p) => runProjectIds.has(p.id))
    : (projects ?? []);

  React.useEffect(() => {
    if (isTokensPage) return;
    if (!projects?.length) return;
    if (!projects.some((p) => p.id === currentProjectId)) {
      setCurrentProject(projects[0].id);
    }
  }, [isTokensPage, projects, currentProjectId, setCurrentProject]);

  const selectedId = isTokensPage ? tokensProjectId : currentProjectId;
  const onProjectChange = isTokensPage
    ? (id: string) => setTokensProjectId(id)
    : setCurrentProject;

  const currentProjectName = selectedId
    ? projectOptions.find((p) => p.id === selectedId)?.name ?? 'Select project'
    : 'Select project';

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl">
      {showProjectFilter ? (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">Project</span>
          <Select
            value={selectedId ?? undefined}
            onValueChange={onProjectChange}
          >
            <SelectTrigger className="h-9 w-auto min-w-[9rem] max-w-[12rem] shrink-0 border-white/[0.08] bg-white/[0.02] px-2.5 text-sm transition-colors hover:border-white/[0.14] [&>span]:truncate">
              <SelectValue placeholder="Select project">{selectedId ? currentProjectName : undefined}</SelectValue>
            </SelectTrigger>
            <SelectContent>
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
