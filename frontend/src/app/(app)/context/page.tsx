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
  const contextProjectId = useUiStore((s) => s.contextProjectId);
  const setContextProjectId = useUiStore((s) => s.setContextProjectId);

  const paramProject = searchParams.get('project');

  React.useEffect(() => {
    if (paramProject) setContextProjectId(paramProject);
  }, [paramProject, setContextProjectId]);

  const projectSlug = contextProjectId ?? 'all';
  const projectName =
    projectSlug === 'all'
      ? 'all projects'
      : projects?.find((p) => p.id === projectSlug)?.name ?? projectSlug;

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Context"
        description={`Shared pipeline context for ${projectName} - PRD summaries, schema notes, and design decisions.`}
      />
      <ContextView projectSlug={projectSlug} />
    </>
  );
}
