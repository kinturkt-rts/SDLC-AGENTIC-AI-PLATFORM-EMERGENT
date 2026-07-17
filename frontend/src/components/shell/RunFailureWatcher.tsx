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

export function RunFailureWatcher() {
  const { data: runs } = useRuns();
  const notifiedRef = React.useRef<Set<string> | null>(null);
  const baselinedRef = React.useRef(false);
  if (notifiedRef.current === null) {
    notifiedRef.current = loadNotified();
  }

  React.useEffect(() => {
    if (!runs?.length) return;
    const notified = notifiedRef.current;
    if (!notified) return;

    // Seed already-failed runs without toasting (login / cold start).
    if (!baselinedRef.current) {
      let seeded = false;
      for (const run of runs) {
        if (run.status === 'failed' && !notified.has(run.id)) {
          notified.add(run.id);
          seeded = true;
        }
      }
      if (seeded) saveNotified(notified);
      baselinedRef.current = true;
      return;
    }

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