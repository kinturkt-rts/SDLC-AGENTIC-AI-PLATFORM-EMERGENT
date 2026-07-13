'use client';

import * as React from 'react';
import { formatDuration, formatRelative } from '@/src/lib/format';

/** Advance wall-clock for live timers. Disabled for finished rows. */
export function useNow(enabled: boolean, intervalMs = 1000): number {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!enabled) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [enabled, intervalMs]);
  return now;
}

function elapsedSeconds(opts: {
  startedAt: string;
  finishedAt?: string | null;
  live: boolean;
  now: number;
  fallbackSec?: number | null;
}): number | null {
  const started = Date.parse(opts.startedAt);
  if (!Number.isFinite(started)) return opts.fallbackSec ?? null;
  if (opts.live) {
    return Math.max(1, Math.floor((opts.now - started) / 1000));
  }
  if (opts.finishedAt) {
    const finished = Date.parse(opts.finishedAt);
    if (Number.isFinite(finished)) {
      return Math.max(1, Math.floor((finished - started) / 1000));
    }
  }
  return opts.fallbackSec ?? null;
}

/** Elapsed duration that ticks every second while `live` is true. */
export function LiveElapsed({
  startedAt,
  finishedAt = null,
  live,
  fallbackSec = null,
  className,
}: {
  startedAt: string;
  finishedAt?: string | null;
  live: boolean;
  fallbackSec?: number | null;
  className?: string;
}) {
  const now = useNow(live);
  const sec = elapsedSeconds({ startedAt, finishedAt, live, now, fallbackSec });
  return <span className={className}>{formatDuration(sec)}</span>;
}

/** "Xm ago" that refreshes every second while `live`. */
export function LiveRelative({
  iso,
  live,
  className,
}: {
  iso: string | null;
  live: boolean;
  className?: string;
}) {
  useNow(live);
  return <span className={className}>{formatRelative(iso)}</span>;
}

/** Run-detail subtitle with ticking start relative + live elapsed. */
export function LiveRunMonitoringLine({
  startedAt,
  live,
}: {
  startedAt: string;
  live: boolean;
}) {
  const now = useNow(live);
  const relative = formatRelative(startedAt);
  const sec = elapsedSeconds({
    startedAt,
    live: true,
    now,
  });
  return (
    <>
      Started {relative} · live for {formatDuration(sec)} · monitoring only (runs on AgentCore)
    </>
  );
}
