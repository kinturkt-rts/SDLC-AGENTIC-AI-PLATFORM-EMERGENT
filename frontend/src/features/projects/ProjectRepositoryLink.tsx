'use client';

import Link from 'next/link';
import { ExternalLink, GitBranch } from 'lucide-react';
import type { Project } from '@/src/types';

export function ProjectRepositoryLink({ project }: { project: Project }) {
  const label = project.repo;
  const href = project.repoHref ?? null;
  const external = project.repoExternal ?? false;

  const content = (
    <>
      <GitBranch className="h-4 w-4 shrink-0 text-teal-400" />
      <span className="text-muted-foreground">Repository</span>
      <code className="rounded-md bg-muted/40 px-1.5 py-0.5 font-mono text-foreground">{label}</code>
      {href ? (
        <ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-teal-400" />
      ) : null}
    </>
  );

  if (!href) {
    return <div className="flex flex-wrap items-center gap-2 text-sm">{content}</div>;
  }

  const className =
    'group inline-flex flex-wrap items-center gap-2 text-sm transition-colors hover:text-teal-400';

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {content}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {content}
    </Link>
  );
}
