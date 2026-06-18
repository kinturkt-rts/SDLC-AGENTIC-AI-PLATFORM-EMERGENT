'use client';

import { Search, ChevronsUpDown } from 'lucide-react';
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

export function Topbar() {
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      <Select value={currentProjectId} onValueChange={setCurrentProject}>
        <SelectTrigger className="h-9 w-[220px] gap-1 border-border">
          <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground" />
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

      <div className="relative ml-auto hidden w-full max-w-sm md:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search runs, agents, artifacts..." className="h-9 pl-9" disabled />
      </div>

      <ThemeToggle />
    </header>
  );
}
