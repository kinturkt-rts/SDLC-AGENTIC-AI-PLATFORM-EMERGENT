'use client';

import * as React from 'react';
import { useUiStore } from '@/src/store/ui-store';

/** Records a run/project visit into the persisted recents list (renders nothing). */
export function RecentTracker({ run, project }: { run?: string; project?: string }) {
  const pushRecentRun = useUiStore((s) => s.pushRecentRun);
  const pushRecentProject = useUiStore((s) => s.pushRecentProject);

  React.useEffect(() => {
    if (run) pushRecentRun(run);
  }, [run, pushRecentRun]);

  React.useEffect(() => {
    if (project) pushRecentProject(project);
  }, [project, pushRecentProject]);

  return null;
}
