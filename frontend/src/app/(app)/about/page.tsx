'use client';

import * as React from 'react';
import Link from 'next/link';
import { Bot, GitBranch, Info, Layers } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { usePlatformSettings } from '@/src/lib/queries';

const APP_VERSION = '0.1.0';

export default function AboutPage() {
  const { data: settings, isLoading } = usePlatformSettings();

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Admin"
        title="About"
        description="Learn what the SDLC Agentic AI Platform does and how a delivery run works."
      />

      <Card className="max-w-2xl border-border/60 bg-card/80 p-5">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 ring-1 ring-teal-500/20">
            <Info className="h-5 w-5 text-teal-600 dark:text-teal-400" />
          </div>
          <div className="min-w-0 space-y-2">
            <h2 className="text-base font-semibold text-foreground">
              {settings?.general.platformName ?? 'SDLC Agentic AI Platform'}
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Turn a short product brief into working applications. Specialist AI agents handle
              requirements, architecture, database design, application code, GitLab publish, and AWS
              deploy - so teams move from idea to a live app faster.
            </p>
          </div>
        </div>
      </Card>

      <div className="grid max-w-2xl gap-4 sm:grid-cols-2">
        <Card className="border-border/60 bg-card/80 p-5">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <h3 className="text-sm font-semibold text-foreground">Version</h3>
          </div>
          {isLoading ? (
            <Skeleton className="mt-3 h-5 w-24" />
          ) : (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Platform</dt>
                <dd className="font-mono text-foreground">{APP_VERSION}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Environment</dt>
                <dd className="text-foreground">
                  {settings?.general.environmentLabel ?? '-'}
                </dd>
              </div>
            </dl>
          )}
        </Card>

        <Card className="border-border/60 bg-card/80 p-5">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-teal-600 dark:text-teal-400" />
            <h3 className="text-sm font-semibold text-foreground">Agents</h3>
          </div>
          {isLoading ? (
            <Skeleton className="mt-3 h-5 w-32" />
          ) : (
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Ready to run</dt>
                <dd className="text-foreground">
                  {settings
                    ? `${settings.pipeline.deployedAgentCount} of ${settings.pipeline.totalAgents}`
                    : '-'}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Outputs stored in</dt>
                <dd className="text-foreground">{settings?.storage.label ?? '-'}</dd>
              </div>
            </dl>
          )}
        </Card>
      </div>

      <Card className="max-w-2xl border-border/60 bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-teal-600 dark:text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">How a run works</h3>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Product → Architect → Database → Developer → GitLab → Deploy
        </p>
        <p className="mt-3 text-sm text-muted-foreground">
          Prefer dark mode or other preferences? Adjust them in{' '}
          <Link href="/settings" className="font-medium text-teal-600 hover:underline dark:text-teal-400">
            Settings
          </Link>
          .
        </p>
      </Card>
    </div>
  );
}
