'use client';

import * as React from 'react';
import Link from 'next/link';
import { ExternalLink, Rocket, X } from 'lucide-react';
import { useUiStore } from '@/src/store/ui-store';

/** Persistent strip so “Open live app” survives toast dismissal and page changes. */
export function LiveAppsBar() {
  const liveApps = useUiStore((s) => s.liveApps);
  const dismissLiveApp = useUiStore((s) => s.dismissLiveApp);

  if (liveApps.length === 0) return null;

  return (
    <div className="border-b border-sky-500/20 bg-sky-500/[0.06] px-4 py-2 sm:px-6">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-sky-300/90">
          <Rocket className="h-3.5 w-3.5" />
          Live apps
        </span>
        {liveApps.map((app) => (
          <div
            key={app.runId}
            className="inline-flex items-center gap-1.5 rounded-md border border-sky-500/25 bg-background/40 px-2 py-1 text-xs"
          >
            <a
              href={app.appUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-sky-300 hover:text-sky-200"
            >
              {app.projectName}
              <ExternalLink className="h-3 w-3 opacity-70" />
            </a>
            <Link href={`/runs/${app.runId}`} className="text-muted-foreground hover:text-foreground">
              run
            </Link>
            <button
              type="button"
              aria-label={`Dismiss ${app.projectName}`}
              onClick={() => dismissLiveApp(app.runId)}
              className="rounded p-0.5 text-muted-foreground/70 hover:bg-white/[0.06] hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
