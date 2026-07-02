'use client';

import * as React from 'react';
import { ExternalLink, GitBranch, Package, Terminal } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import type { RunHandoffs } from '@/src/types';

function MetaLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-sm text-teal-400 hover:text-teal-300"
    >
      {label}
      <ExternalLink className="h-3.5 w-3.5" />
    </a>
  );
}

function HandoffSection({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof GitBranch;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 border-b border-white/[0.06] px-4 py-4 last:border-0">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5 text-teal-400" />
        {title}
      </h3>
      {children}
    </div>
  );
}

export function PipelineHandoffsCard({ handoffs }: { handoffs: RunHandoffs }) {
  const gitlab = handoffs.gitlab;
  const developer = handoffs.developer;
  const branchUrl = gitlab?.branchUrl ?? null;
  const mrUrl = gitlab?.mergeRequestUrl ?? handoffs.contextMergeRequestUrl ?? null;
  const branch = gitlab?.branch ?? handoffs.contextFeatureBranch ?? null;
  const hasAnything = Boolean(gitlab || developer || mrUrl || branch);

  if (!hasAnything) {
    return null;
  }

  return (
    <Card className="border-white/[0.06] bg-card/80">
      <div className="border-b border-white/[0.06] px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Pipeline metadata</h2>
      </div>

      {gitlab ? (
        <HandoffSection title="GitLab publish" icon={GitBranch}>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              status={gitlab.status === 'published' ? 'completed' : gitlab.status === 'failed' ? 'failed' : 'running'}
              size="sm"
            />
            {branch ? (
              <span className="rounded-md bg-muted/50 px-2 py-0.5 font-mono text-xs text-foreground">{branch}</span>
            ) : null}
            {gitlab.gitlabProject ? (
              <span className="truncate text-xs text-muted-foreground">{gitlab.gitlabProject}</span>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5 pt-1">
            {branchUrl ? <MetaLink href={branchUrl} label="View branch on GitLab" /> : null}
            {mrUrl ? <MetaLink href={mrUrl} label="Open merge request" /> : null}
            {gitlab.pathsPublishedCount > 0 ? (
              <p className="text-xs text-muted-foreground">{gitlab.pathsPublishedCount} paths published</p>
            ) : null}
            {gitlab.error ? <p className="text-xs text-red-400">{gitlab.error}</p> : null}
          </div>
        </HandoffSection>
      ) : developer ? (
        <HandoffSection title="GitLab publish" icon={GitBranch}>
          <p className="text-sm text-muted-foreground">
            Skipped — no GitLab handoff for this run.
          </p>
        </HandoffSection>
      ) : null}

      {developer ? (
        <HandoffSection title="Developer handoff" icon={Package}>
          <p className="text-sm text-foreground">
            <span className="font-mono">{developer.targetApp || handoffs.projectSlug}</span>
            {' · '}
            {developer.writtenFilesCount} files
          </p>
          {developer.testCommand ? (
            <div className="flex items-start gap-2 rounded-md border border-white/[0.06] bg-muted/20 px-3 py-2">
              <Terminal className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <code className="break-all font-mono text-xs text-foreground">{developer.testCommand}</code>
            </div>
          ) : null}
          {developer.runCommand ? (
            <p className="font-mono text-[11px] text-muted-foreground">Run: {developer.runCommand}</p>
          ) : null}
        </HandoffSection>
      ) : null}
    </Card>
  );
}
