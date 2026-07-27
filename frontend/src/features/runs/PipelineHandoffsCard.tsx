'use client';

import * as React from 'react';
import { ExternalLink } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { StatusBadge } from '@/src/components/common/StatusBadge';
import { OpenLiveAppLink } from '@/src/components/common/OpenLiveAppLink';
import type { RunHandoffs, StepStatus } from '@/src/types';

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

function MetadataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 px-4 py-2.5 sm:flex-row sm:items-center sm:gap-4">
      <dt className="w-40 shrink-0 text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm text-foreground">{value}</dd>
    </div>
  );
}

function handoffBadge(status: string): 'completed' | 'failed' | 'running' | 'queued' {
  const normalized = status.trim().toLowerCase();
  if (normalized === 'completed' || normalized === 'published' || normalized === 'already-published' || normalized === 'healthy' || normalized === 'deployed') {
    return 'completed';
  }
  if (normalized === 'failed' || normalized === 'error') return 'failed';
  if (normalized === 'in_progress' || normalized === 'running' || normalized === 'deploying' || normalized === 'tf_ready') {
    return 'running';
  }
  return 'queued';
}

function resolveValidationLabel(
  validationStatus: 'passed' | 'failed' | null | undefined,
  developerStepStatus?: StepStatus,
): { label: string; badge: 'completed' | 'failed' | 'running' | 'queued' } | null {
  if (validationStatus === 'passed') {
    return { label: 'Tests passed', badge: 'completed' };
  }
  if (validationStatus === 'failed') {
    return { label: 'Tests failed', badge: 'failed' };
  }
  if (developerStepStatus === 'completed') {
    return { label: 'Tests passed', badge: 'completed' };
  }
  if (developerStepStatus === 'failed') {
    return { label: 'Tests failed', badge: 'failed' };
  }
  if (developerStepStatus === 'running') {
    return { label: 'Validation in progress', badge: 'running' };
  }
  if (developerStepStatus === 'queued' || developerStepStatus === 'skipped') {
    return null;
  }
  return null;
}

export function PipelineHandoffsCard({
  handoffs,
  developerStepStatus,
}: {
  handoffs: RunHandoffs;
  developerStepStatus?: StepStatus;
}) {
  const gitlab = handoffs.gitlab;
  const developer = handoffs.developer;
  const devops = handoffs.devops;
  const branchUrl = gitlab?.branchUrl ?? null;
  const mrUrl = gitlab?.mergeRequestUrl ?? handoffs.contextMergeRequestUrl ?? null;
  const appUrl = devops?.appUrl ?? null;
  const hasAnything = Boolean(developer || gitlab || devops || branchUrl || mrUrl || appUrl);

  if (!hasAnything) {
    return null;
  }

  const appName = developer?.targetApp || devops?.targetApp || handoffs.projectSlug;
  const validation = resolveValidationLabel(developer?.validationStatus ?? null, developerStepStatus);

  return (
    <Card className="border-white/[0.06] bg-card/80">
      <div className="border-b border-white/[0.06] px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Pipeline metadata</h2>
      </div>

      <dl className="divide-y divide-white/[0.06]">
        {developer ? (
          <>
            <MetadataRow label="App name" value={<span className="font-medium">{appName}</span>} />
            <MetadataRow
              label="Files generated"
              value={`${developer.writtenFilesCount.toLocaleString()} file${developer.writtenFilesCount === 1 ? '' : 's'}`}
            />
            <MetadataRow
              label="Developer handoff"
              value={
                <StatusBadge
                  status={handoffBadge(developer.status)}
                  size="sm"
                  label={developer.status.replaceAll('_', ' ')}
                />
              }
            />
            {developer.error ? (
              <MetadataRow label="Developer error" value={<span className="text-red-400">{developer.error}</span>} />
            ) : null}
            {validation ? (
              <MetadataRow
                label="Validation"
                value={<StatusBadge status={validation.badge} size="sm" label={validation.label} />}
              />
            ) : null}
          </>
        ) : null}

        {gitlab ? (
          <div className="space-y-2 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">GitLab</p>
            <div className="flex flex-col gap-1.5">
              <StatusBadge
                status={handoffBadge(gitlab.status)}
                size="sm"
                label={gitlab.status.replaceAll('_', ' ')}
              />
              {branchUrl ? <MetaLink href={branchUrl} label="View branch on GitLab" /> : null}
              {mrUrl ? <MetaLink href={mrUrl} label="Open merge request" /> : null}
            </div>
            {gitlab?.error ? <p className="text-xs text-red-400">{gitlab.error}</p> : null}
          </div>
        ) : null}

        {devops || appUrl ? (
          <div className="space-y-2 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Deploy</p>
            <div className="flex flex-col gap-1.5">
              {devops ? (
                <StatusBadge
                  status={handoffBadge(devops.status)}
                  size="sm"
                  label={devops.status.replaceAll('_', ' ')}
                />
              ) : null}
              {appUrl ? (
                <OpenLiveAppLink href={appUrl} variant="button" />
              ) : (
                <p className="text-xs text-muted-foreground">Live URL appears here after devops-agent finishes deploy.</p>
              )}
              {devops?.environment ? (
                <p className="text-xs text-muted-foreground">
                  Env {devops.environment}
                  {devops.region ? ` · ${devops.region}` : ''}
                  {devops.ecsService ? ` · ${devops.ecsService}` : ''}
                </p>
              ) : null}
            </div>
            {devops?.error ? <p className="text-xs text-red-400">{devops.error}</p> : null}
          </div>
        ) : null}
      </dl>
    </Card>
  );
}
