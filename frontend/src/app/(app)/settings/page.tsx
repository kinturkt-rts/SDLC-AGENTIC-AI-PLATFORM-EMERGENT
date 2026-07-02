'use client';

import * as React from 'react';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import {
  Server,
  Palette,
  Lock,
  Info,
  Database,
  Workflow,
  ExternalLink,
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
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-white/[0.04] py-3 last:border-0 last:pb-0 first:pt-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          'text-sm font-medium text-foreground sm:text-right',
          mono && 'font-mono text-xs break-all',
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function ModeBadge({ ok, label }: { ok?: boolean; label: string }) {
  return (
    <span
      className={cn(
        'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide',
        ok
          ? 'bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/20'
          : 'bg-muted/50 text-muted-foreground ring-1 ring-white/[0.06]',
      )}
    >
      {label}
    </span>
  );
}

function PlatformSection({ settings }: { settings: PlatformSettings }) {
  const { connection, storage, pipeline } = settings;

  return (
    <>
      <Card className="border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">Connection</h3>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          How this control plane reads platform state. Configured via environment variables — restart{' '}
          <code className="rounded bg-muted/40 px-1 font-mono text-xs">npm run dev</code> after changes.
        </p>
        <dl className="mt-4">
          <SettingRow
            label="Data mode"
            value={
              <ModeBadge
                ok={connection.mode === 'local'}
                label={connection.mode === 'local' ? 'Local bridge' : 'Remote API'}
              />
            }
          />
          <SettingRow
            label="API base URL"
            value={connection.apiBaseUrl ?? '— (uses /api/v1)'}
            mono
          />
          <SettingRow label="Summary" value={connection.description} />
        </dl>
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-white/[0.06] bg-muted/20 p-3 text-xs text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <p>
            Set <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> in{' '}
            <code className="font-mono">frontend/.env.local</code> to point at a deployed platform API.
            Leave unset for local development (current default).
          </p>
        </div>
      </Card>

      <Card className="border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">Artifacts &amp; cloud</h3>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Where pipeline outputs and run context are stored. Loaded from {settings.envSource}.
        </p>
        <dl className="mt-4">
          <SettingRow
            label="Artifact store"
            value={
              <ModeBadge ok={storage.artifactStore === 's3'} label={storage.artifactStore} />
            }
          />
          {storage.s3Bucket ? (
            <SettingRow label="S3 bucket" value={storage.s3Bucket} mono />
          ) : null}
          <SettingRow label="AWS region" value={storage.awsRegion ?? '—'} mono />
          <SettingRow label="AWS profile" value={storage.awsProfile ?? '— (default credential chain)'} mono />
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
              Agents <ExternalLink className="h-3 w-3" />
            </Link>
          </Button>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          How runs invoke specialist agents when you submit from the dashboard.
        </p>
        <dl className="mt-4">
          <SettingRow
            label="Transport"
            value={<ModeBadge ok={pipeline.transport === 'a2a'} label={pipeline.transport} />}
          />
          <SettingRow label="AgentCore region" value={pipeline.agentcoreRegion ?? '—'} mono />
          <SettingRow
            label="Deployed MVP agents"
            value={`${pipeline.deployedAgentCount} online`}
          />
        </dl>
        <p className="mt-4 text-xs text-muted-foreground">
          <code className="font-mono">SDLC_PIPELINE_TRANSPORT</code> —{' '}
          <span className="font-mono">local</span>, <span className="font-mono">a2a</span>, or{' '}
          <span className="font-mono">auto</span>. AgentCore runtimes are tracked in{' '}
          <code className="font-mono">backend/config/agentcore/runtimes.json</code>.
        </p>
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
        description="Read-only platform configuration and personal preferences. Environment values are loaded at server start — not editable in the UI yet."
      />

      {isLoading ? (
        <div className="grid max-w-2xl gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-xl" />
          ))}
        </div>
      ) : isError || !settings ? (
        <Card className="max-w-2xl border-red-500/20 bg-card/80 p-5 text-sm text-muted-foreground">
          Could not load platform settings. Ensure the dev server can read backend env files.
        </Card>
      ) : (
        <div className="grid max-w-2xl gap-4">
          <PlatformSection settings={settings} />
        </div>
      )}

      <Card className="max-w-2xl border-white/[0.06] bg-card/80 p-5">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-teal-400" />
          <h3 className="text-sm font-semibold text-foreground">Appearance</h3>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Dark mode</p>
            <p className="text-xs text-muted-foreground">Saved in your browser for this device.</p>
          </div>
          <Switch
            checked={mounted ? theme === 'dark' : true}
            onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
          />
        </div>
      </Card>

      <Card className="max-w-2xl border-white/[0.06] bg-card/60 p-5 opacity-70">
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Authentication</h3>
          <span className="rounded-md bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Coming soon
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          SSO / OIDC sign-in will be configured here once the platform API is available.
        </p>
        <Button className="mt-4" variant="outline" disabled>
          Configure provider
        </Button>
      </Card>
    </div>
  );
}
