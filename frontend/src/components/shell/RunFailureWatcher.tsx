'use client';

import * as React from 'react';
import { toast } from 'sonner';
import { useRuns } from '@/src/lib/queries';

const NOTIFIED_KEY = 'sdlc:notified-failed-runs';

function loadNotified(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = window.sessionStorage.getItem(NOTIFIED_KEY);
    return raw ? new Set(JSON.parse(raw) as string[]) : new Set();
  } catch {
    return new Set();
  }
}

function saveNotified(ids: Set<string>) {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(NOTIFIED_KEY, JSON.stringify(Array.from(ids)));
  } catch {
    // sessionStorage unavailable (private mode, quota, etc.) - non-fatal, just skip persistence.
  }
}

/**
 * App-shell-level watcher: fires a toast the first time any run is observed as
 * "failed", regardless of which page the user is currently on (dashboard, logs,
 * artifacts, ...). Piggybacks entirely on the existing useRuns() polling query -
 * no new network calls, no change to polling cadence. "Already notified" run ids
 * are kept in sessionStorage so a page refresh doesn't re-toast the same failure.
 */
export function RunFailureWatcher() {
  const { data: runs } = useRuns();
  const notifiedRef = React.useRef<Set<string> | null>(null);
  if (notifiedRef.current === null) {
    notifiedRef.current = loadNotified();
  }

  React.useEffect(() => {
    if (!runs?.length) return;
    const notified = notifiedRef.current;
    if (!notified) return;
    let changed = false;
    for (const run of runs) {
      if (run.status === 'failed' && !notified.has(run.id)) {
        notified.add(run.id);
        changed = true;
        toast.error(`Run failed: ${run.projectName || run.id}`, {
          description: run.error || 'Open the run detail page to see the failure reason.',
        });
      }
    }
    if (changed) saveNotified(notified);
  }, [runs]);

  return null;
}