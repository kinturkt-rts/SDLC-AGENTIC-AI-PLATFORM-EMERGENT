'use client';

import { usePathname } from 'next/navigation';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ThemeToggle } from '@/src/components/common/ThemeToggle';
import { useUiStore } from '@/src/store/ui-store';
import { useProjects } from '@/src/lib/queries';

/** Pages that scope content by project — hide global filter on dashboard. */
function useShowProjectFilter(): boolean {
  const pathname = usePathname();
  if (pathname === '/dashboard') return false;
  return pathname.startsWith('/artifacts') || pathname.startsWith('/pipelines');
}

export function Topbar() {
  const showProjectFilter = useShowProjectFilter();
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/60 bg-background/70 px-4 backdrop-blur-xl">
      {showProjectFilter ? (
        <Select value={currentProjectId} onValueChange={setCurrentProject}>
          <SelectTrigger className="h-9 w-auto min-w-[9rem] max-w-[11rem] shrink-0 border-white/[0.08] bg-white/[0.02] px-2.5 text-sm transition-colors hover:border-white/[0.14] [&>span]:truncate">
            <SelectValue placeholder="Select project" />
          </SelectTrigger>
          <SelectContent>
            {projects?.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : null}

      <div className={`relative hidden w-full max-w-sm md:block ${showProjectFilter ? 'ml-auto' : ''}`}>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
        <Input
          placeholder="Search runs, agents, artifacts..."
          className="h-9 border-white/[0.06] bg-white/[0.02] pl-9 text-sm placeholder:text-muted-foreground/40 focus:border-teal-500/30 focus:ring-teal-500/10"
          disabled
        />
      </div>

      <ThemeToggle />
    </header>
  );
}
