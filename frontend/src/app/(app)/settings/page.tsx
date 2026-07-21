'use client';

import * as React from 'react';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import {
  Palette,
  Lock,
  Settings2,
  Workflow,
  HardDrive,
  ExternalLink,
  Shield,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/src/components/common/PageHeader';
import { usePlatformSettings } from '@/src/lib/queries';
import type { PlatformSettings } from '@/src/lib/platform-settings';

function SettingRow({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-white/[0.04] py-3 last:border-0 last:pb-0 first:pt-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium text-foreground sm:text-right">{value}</dd>
    </div>
  );
}

function StatusPill({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'success' | 'muted' }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1',
        tone === 'success' && 'bg-emerald-500/10 text-emerald-400 ring-emerald-500/20',
        tone === 'muted' && 'bg-muted/40 text-muted-foreground ring-white/[0.06]',
        tone === 'neutral' && 'bg-teal-500/10 text-teal-400 ring-teal-500/20',
      )}
    >
      {children}
    </span>
  );
}

function PlatformSettingsCards({ settings }: { settings: PlatformSettings }) {
  const { general, storage, pipeline } = settings;

  return (
    <>
      <Card className="border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <Settings2 className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">General</h3>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Platform identity and where pipeline artifacts are stored.
        </p>
        <dl className="mt-4">
          <SettingRow label="Platform" value={general.platformName} />
          <SettingRow
            label="Environment"
            value={
              <StatusPill tone={general.environment === 'production' ? 'success' : 'neutral'}>
                {general.environmentLabel}
              </StatusPill>
            }
          />
          <SettingRow
            label="Artifact storage"
            value={
              <span className="inline-flex items-center gap-1.5">
                <HardDrive className="h-3.5 w-3.5 text-muted-foreground" />
                {storage.label}
              </span>
            }
          />
        </dl>
      </Card>

      <Card className="border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-teal-400" />
            <h3 className="text-sm font-semibold text-foreground">Pipeline</h3>
          </div>
          <Button asChild variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground">
            <Link href="/agents">
              View agents <ExternalLink className="h-3 w-3" />
            </Link>
          </Button>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Specialist agents that run when you submit a brief from the dashboard.
        </p>
        <dl className="mt-4">
          <SettingRow
            label="Agents available"
            value={`${pipeline.deployedAgentCount} of ${pipeline.totalAgents} deployed`}
          />
          <SettingRow
            label="Default flow"
            value="Product → Architect → Database → Developer → GitLab"
          />
        </dl>
      </Card>
    </>
  );
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const { data: settings, isLoading, isError } = usePlatformSettings();

  React.useEffect(() => setMounted(true), []);

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Admin"
        title="Settings"
        description="Platform preferences and account options for this control plane."
      />

      {isLoading ? (
        <div className="grid max-w-2xl gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-xl" />
          ))}
        </div>
      ) : isError || !settings ? (
        <Card className="max-w-2xl border-red-500/20 bg-card/80 p-5 text-sm text-muted-foreground">
          Could not load platform settings. Restart the dev server if you recently changed environment files.
        </Card>
      ) : (
        <div className="grid max-w-2xl gap-4">
          <PlatformSettingsCards settings={settings} />
        </div>
      )}

      <Card className="max-w-2xl border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">Appearance</h3>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm font-medium text-foreground">Dark mode</p>
          <Switch
            checked={mounted ? theme === 'dark' : true}
            onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
          />
        </div>
      </Card>

      <Card className="max-w-2xl border-white/[0.06] bg-card/60 p-5 opacity-80">
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Authentication</h3>
          <span className="rounded-md bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-400">
            Wired
          </span>
        </div>
        <div className="mt-3 flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-500/10 ring-1 ring-orange-500/20">
            <Shield className="h-4 w-4 text-orange-400" />
          </div>
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium text-foreground">Amazon Cognito</p>
            <p className="text-sm text-muted-foreground">
              Control-plane UI sign-in uses a Cognito User Pool (email + password, forgot-password).
              Users and password hashes live in Cognito — not in agents, S3 runs, or the pipeline.
              Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID on the control-plane service.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
