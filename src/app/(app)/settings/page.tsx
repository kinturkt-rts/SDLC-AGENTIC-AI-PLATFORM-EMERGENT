'use client';

import * as React from 'react';
import { useTheme } from 'next-themes';
import { Server, Palette, Lock, Info } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { PageHeader } from '@/src/components/common/PageHeader';
import { API_BASE_URL, USING_MOCKS } from '@/src/lib/api';

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const [apiBase, setApiBase] = React.useState(API_BASE_URL);
  React.useEffect(() => setMounted(true), []);

  return (
    <>
      <PageHeader eyebrow="Admin" title="Settings" description="Configure the control plane. Settings are session-only in this build." />

      <Card className="max-w-2xl p-5">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-teal-500" />
          <h3 className="text-sm font-semibold text-foreground">Platform API</h3>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">Base URL of the SDLC platform REST API. Read from <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code>.</p>
        <div className="mt-4 space-y-2">
          <Label htmlFor="api-base">API base URL</Label>
          <Input id="api-base" value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="https://api.platform.internal" />
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-2.5 text-xs text-muted-foreground">
            <Info className="h-3.5 w-3.5 shrink-0" />
            {USING_MOCKS
              ? 'No API base configured — the UI is serving typed mock data. Set NEXT_PUBLIC_API_BASE_URL to connect to a live platform.'
              : `Connected to ${API_BASE_URL}.`}
          </div>
        </div>
      </Card>

      <Card className="max-w-2xl p-5">
        <div className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-teal-500" />
          <h3 className="text-sm font-semibold text-foreground">Appearance</h3>
        </div>
        <div className="mt-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Dark mode</p>
            <p className="text-xs text-muted-foreground">Toggle between light and dark themes.</p>
          </div>
          <Switch checked={mounted ? theme === 'dark' : true} onCheckedChange={(c) => setTheme(c ? 'dark' : 'light')} />
        </div>
      </Card>

      <Card className="max-w-2xl p-5 opacity-80">
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Authentication</h3>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">Coming soon</span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">SSO / OIDC sign-in will be configured here once the platform API is available.</p>
        <Button className="mt-4" variant="outline" disabled>Configure provider</Button>
      </Card>
    </>
  );
}
