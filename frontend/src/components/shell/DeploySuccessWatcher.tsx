'use client';

import * as React from 'react';
import { toast } from 'sonner';
import { useProjects, useRunHandoffs, useRuns } from '@/src/lib/queries';

const NOTIFIED_KEY = 'sdlc:notified-live-apps';
const BASELINE_MS = 3_000;

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
    // ignore
  }
}

/**
 * Watches runs for a devops live URL and toasts once when an app goes live.
 * Persistent access lives on the project page / run handoffs — not a global bar.
 */
function DeployHandoffProbe({
  runId,
  projectId,
  projectName,
  onLive,
}: {
  runId: string;
  projectId: string;
  projectName: string;
  onLive: (info: { runId: string; projectId: string; projectName: string; appUrl: string }) => void;
}) {
  const { data: handoffs } = useRunHandoffs(runId, true);
  const appUrl = handoffs?.devops?.appUrl?.trim() || null;

  React.useEffect(() => {
    if (!appUrl) return;
    onLive({ runId, projectId, projectName, appUrl });
  }, [appUrl, runId, projectId, projectName, onLive]);

  return null;
}

export function DeploySuccessWatcher() {
  const { data: runs } = useRuns();
  const { data: projects } = useProjects();
  const notifiedRef = React.useRef<Set<string> | null>(null);
  const mountedAtRef = React.useRef(0);

  if (notifiedRef.current === null) {
    notifiedRef.current = loadNotified();
  }
  if (mountedAtRef.current === 0 && typeof window !== 'undefined') {
    mountedAtRef.current = Date.now();
  }

  // Seed "already notified" from projects that already have a liveUrl (no toast on cold start).
  React.useEffect(() => {
    if (!projects?.length) return;
    for (const p of projects) {
      if (!p.liveUrl || !p.runId) continue;
      notifiedRef.current?.add(p.runId);
    }
    if (notifiedRef.current) saveNotified(notifiedRef.current);
  }, [projects]);

  const candidates = React.useMemo(() => {
    return (runs ?? [])
      .filter((r) => r.status === 'completed' || r.status === 'running')
      .slice(0, 12)
      .map((r) => ({ runId: r.id, projectId: r.projectId, projectName: r.projectName }));
  }, [runs]);

  const onLive = React.useCallback(
    (info: { runId: string; projectId: string; projectName: string; appUrl: string }) => {
      const notified = notifiedRef.current;
      if (!notified) return;
      if (notified.has(info.runId)) return;

      notified.add(info.runId);
      saveNotified(notified);

      const inBaseline = Date.now() - mountedAtRef.current < BASELINE_MS;
      if (inBaseline) return;

      toast.success(`${info.projectName} is live`, {
        description: 'Open it from the project page anytime, or use Open app now.',
        duration: 12_000,
        action: {
          label: 'Open app',
          onClick: () => {
            window.open(info.appUrl, '_blank', 'noopener,noreferrer');
          },
        },
      });
    },
    [],
  );

  return (
    <>
      {candidates.map((c) => (
        <DeployHandoffProbe
          key={c.runId}
          runId={c.runId}
          projectId={c.projectId}
          projectName={c.projectName}
          onLive={onLive}
        />
      ))}
    </>
  );
}
