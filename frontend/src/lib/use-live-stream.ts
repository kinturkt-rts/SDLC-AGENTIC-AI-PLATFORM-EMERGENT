'use client';

import * as React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys, type LogsFilter } from '@/src/lib/queries';
import type {
  DashboardSummary,
  PipelineRun,
  LogEntry,
  RunEvent,
  RunHandoffs,
} from '@/src/types';
import type { ActivityFeedItem } from '@/src/lib/run-events';

/**
 * Opens an SSE connection and writes pushed data into the React Query cache so
 * existing hooks (useDashboardSummary / useRuns / useRecentActivity / useLogs)
 * render live updates without interval polling. Returns { connected } so callers
 * can fall back to polling if the stream drops.
 */
function useEventStream(
  url: string,
  handlers: Record<string, (data: unknown) => void>,
  enabled = true,
): { connected: boolean } {
  const [connected, setConnected] = React.useState(false);
  // Keep latest handlers without reopening the connection.
  const handlersRef = React.useRef(handlers);
  handlersRef.current = handlers;

  React.useEffect(() => {
    if (!enabled) {
      setConnected(false);
      return;
    }
    const es = new EventSource(url);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    for (const event of Object.keys(handlersRef.current)) {
      es.addEventListener(event, (e: MessageEvent) => {
        try {
          handlersRef.current[event]?.(JSON.parse(e.data));
        } catch {
          /* ignore malformed frame */
        }
      });
    }
    return () => {
      setConnected(false);
      es.close();
    };
  }, [url, enabled]);

  return { connected };
}

interface DashboardStreamPayload {
  summary: DashboardSummary;
  runs: PipelineRun[];
  activity: ActivityFeedItem[];
}

export function useLiveDashboard(enabled = true): { connected: boolean } {
  const queryClient = useQueryClient();
  return useEventStream(
    '/api/v1/stream?topic=dashboard',
    {
      dashboard: (data) => {
        const p = data as DashboardStreamPayload;
        if (p.summary) queryClient.setQueryData(queryKeys.dashboard, p.summary);
        if (p.runs) queryClient.setQueryData(queryKeys.runs, p.runs);
        if (p.activity) queryClient.setQueryData(queryKeys.activity, p.activity);
      },
    },
    enabled,
  );
}

export function useLiveLogs(filters: LogsFilter, enabled = true): { connected: boolean } {
  const queryClient = useQueryClient();
  const params = new URLSearchParams({ topic: 'logs' });
  if (filters.runId) params.set('runId', filters.runId);
  if (filters.agent) params.set('agent', filters.agent);
  if (filters.minutes) params.set('minutes', String(filters.minutes));
  if (filters.limit) params.set('limit', String(filters.limit));
  const url = `/api/v1/stream?${params.toString()}`;

  return useEventStream(
    url,
    {
      logs: (data) => {
        const p = data as { logs: LogEntry[] };
        if (p.logs) queryClient.setQueryData([...queryKeys.logs, filters], p.logs);
      },
    },
    enabled,
  );
}

interface RunStreamPayload {
  run: PipelineRun | null;
  events: RunEvent[];
  logs: LogEntry[];
  handoffs: RunHandoffs | null;
}

export function useLiveRun(runId: string, enabled = true): { connected: boolean } {
  const queryClient = useQueryClient();
  return useEventStream(
    `/api/v1/stream?topic=run&runId=${encodeURIComponent(runId)}`,
    {
      run: (data) => {
        const p = data as RunStreamPayload;
        if (p.run) queryClient.setQueryData(queryKeys.run(runId), p.run);
        if (p.events) queryClient.setQueryData(queryKeys.runEvents(runId), p.events);
        if (p.logs) queryClient.setQueryData(queryKeys.runLogs(runId), p.logs);
        if (p.handoffs) queryClient.setQueryData(queryKeys.runHandoffs(runId), p.handoffs);
      },
    },
    enabled && Boolean(runId),
  );
}
