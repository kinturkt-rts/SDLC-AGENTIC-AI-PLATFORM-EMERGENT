'use client';

import { Search, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
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
import type { Environment } from '@/src/types';

const ENV_STYLES: Record<Environment, string> = {
  dev: 'bg-slate-100 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700',
  staging: 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900',
  prod: 'bg-red-50 text-red-700 ring-red-200 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-900',
};

export function Topbar() {
  const { data: projects } = useProjects();
  const currentProjectId = useUiStore((s) => s.currentProjectId);
  const setCurrentProject = useUiStore((s) => s.setCurrentProject);
  const environment = useUiStore((s) => s.environment);
  const setEnvironment = useUiStore((s) => s.setEnvironment);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      <Select value={currentProjectId} onValueChange={setCurrentProject}>
        <SelectTrigger className="h-9 w-[200px] gap-1 border-border">
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

      <Select value={environment} onValueChange={(v) => setEnvironment(v as Environment)}>
        <SelectTrigger className={cn('h-9 w-[120px] gap-1.5 font-medium ring-1 ring-inset', ENV_STYLES[environment])}>
          <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="dev">dev</SelectItem>
          <SelectItem value="staging">staging</SelectItem>
          <SelectItem value="prod">prod</SelectItem>
        </SelectContent>
      </Select>

      <div className="relative ml-auto hidden w-full max-w-sm md:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search runs, agents, artifacts..."
          className="h-9 pl-9"
          disabled
        />
      </div>

      <ThemeToggle />
    </header>
  );
}
