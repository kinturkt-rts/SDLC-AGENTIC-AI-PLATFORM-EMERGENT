'use client';

import * as React from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { ContextView } from '@/src/features/context/ContextView';
import { useProjects } from '@/src/lib/queries';
import { useUiStore } from '@/src/store/ui-store';

export default function ContextPage() {
  return (
    <React.Suspense fallback={<Skeleton className="h-72 w-full rounded-lg" />}>
      <ContextInner />
    </React.Suspense>
  );
}

function ContextInner() {
  const searchParams = useSearchParams();
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);

  const paramProject = searchParams.get('project');
  const [selected, setSelected] = React.useState<string>(paramProject ?? currentProjectId);

  // Default to the top-bar selected project unless a ?project= override is present.
  React.useEffect(() => {
    if (!paramProject) setSelected(currentProjectId);
  }, [currentProjectId, paramProject]);

  React.useEffect(() => {
    if (paramProject) setSelected(paramProject);
  }, [paramProject]);

  const projectName = projects?.find((p) => p.id === selected)?.name;
  const subtitle =
    selected === 'all'
      ? 'Shared context across all projects.'
      : `Context for ${projectName ?? selected}`;

  return (
    <>
      <PageHeader
        eyebrow="Assets"
        title="Context"
        description={subtitle}
        actions={
          <Select value={selected} onValueChange={setSelected}>
            <SelectTrigger className="h-9 w-[220px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All projects</SelectItem>
              {projects?.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />
      <ContextView projectSlug={selected} />
    </>
  );
}
