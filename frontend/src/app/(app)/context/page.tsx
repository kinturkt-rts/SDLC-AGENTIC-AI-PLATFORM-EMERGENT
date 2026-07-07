'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { ContextView } from '@/src/features/context/ContextView';
import { useProjects } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';

export default function ContextPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-72 w-full rounded-xl" />}>
      <ContextInner />
    </React.Suspense>
  );
}

function ContextInner() {
  const searchParams = useSearchParams();
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);

  const paramProject = searchParams.get('project');

  React.useEffect(() => {
    if (paramProject) setCurrentProject(paramProject);
  }, [paramProject, setCurrentProject]);

  const projectName = projects?.find((p) => p.id === currentProjectId)?.name ?? currentProjectId;

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Context"
        description={`Shared pipeline context for ${projectName} - PRD summaries, schema notes, and design decisions.`}
      />
      <ContextView projectSlug={currentProjectId} />
    </>
  );
}
