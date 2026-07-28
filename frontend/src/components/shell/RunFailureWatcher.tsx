'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useRuns } from '@/src/lib/queries';

const NOTIFIED_KEY = 'sdlc:notified-failed-runs';
const TOAST_DESCRIPTION_MAX_CHARS = 160;

/** Toasts are for a brief notification, not a wall of raw subprocess output —
 * show only the first line (up to a length cap); the run detail page has the
 * full text. */
export function summarizeRunError(error: string): string {
  const firstLine = error.split('\n')[0]?.trim() || error.trim();
  if (firstLine.length <= TOAST_DESCRIPTION_MAX_CHARS) return firstLine;
  return `${firstLine.slice(0, TOAST_DESCRIPTION_MAX_CHARS - 1).trimEnd()}…`;
}

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
  const router = useRouter();
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
          description: run.error
            ? summarizeRunError(run.error)
            : 'Open the run detail page to see the failure reason.',
          action: {
            label: 'View details',
            onClick: () => router.push(`/runs/${run.id}`),
          },
        });
      }
    }
    if (changed) saveNotified(notified);
  }, [runs]);

  return null;
}