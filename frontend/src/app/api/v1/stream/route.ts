import {
  getDashboardSummary,
  listRuns,
  listRecentActivity,
  getRun,
  listRunEvents,
  listRunLogs,
} from '@/src/lib/repo-reader';
import { getRunHandoffs } from '@/src/lib/pipeline-handoffs';
import { listCloudWatchLogs } from '@/src/lib/cloudwatch-logs';
import { parseLogAgentQuery } from '@/src/lib/pipeline-phases';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const DASHBOARD_INTERVAL_MS = 5000;
const LOGS_INTERVAL_MS = 5000;
const HEARTBEAT_MS = 15000;

async function dashboardPayload() {
  const [summary, runs, activity] = await Promise.all([
    getDashboardSummary(),
    listRuns(),
    listRecentActivity(12),
  ]);
  return { summary, runs, activity };
}

async function logsPayload(searchParams: URLSearchParams) {
  const runId = searchParams.get('runId')?.trim() || undefined;
  const agent = parseLogAgentQuery(searchParams.get('agent'));
  const minutesRaw = searchParams.get('minutes');
  let minutes: number | undefined;
  if (minutesRaw) {
    const parsed = Number.parseInt(minutesRaw, 10);
    if (Number.isFinite(parsed) && parsed > 0) minutes = parsed;
  }
  const limitRaw = searchParams.get('limit');
  let limit = 1000;
  if (limitRaw) {
    const parsed = Number.parseInt(limitRaw, 10);
    if (Number.isFinite(parsed) && parsed > 0) limit = parsed;
  }

  if (runId) {
    const run = await getRun(runId);
    if (run) {
      const startMs = Date.parse(run.startedAt) - 2 * 60_000;
      const endMs = run.finishedAt ? Date.parse(run.finishedAt) + 5 * 60_000 : undefined;
      const logs = await listCloudWatchLogs({
        runId,
        startMs,
        endMs,
        agent,
        limit,
        mvpOnly: true,
        timeWindowForRun: true,
      });
      return { logs };
    }
  }
  const logs = await listCloudWatchLogs({ agent, minutes: minutes ?? 240, limit, mvpOnly: true });
  return { logs };
}

async function runPayload(runId: string) {
  const run = await getRun(runId);
  if (!run) return { run: null, events: [], logs: [], handoffs: null };
  const [events, logs, handoffs] = await Promise.all([
    listRunEvents(runId),
    listRunLogs(runId),
    getRunHandoffs(run.id, run.projectId),
  ]);
  return { run, events, logs, handoffs };
}

/**
 * Server-Sent Events stream. One persistent connection replaces client polling.
 *   /api/v1/stream?topic=dashboard
 *   /api/v1/stream?topic=logs&runId=&agent=&minutes=&limit=
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const topicParam = searchParams.get('topic');
  const topic = topicParam === 'logs' ? 'logs' : topicParam === 'run' ? 'run' : 'dashboard';
  const runId = searchParams.get('runId')?.trim() || '';
  const intervalMs = topic === 'dashboard' ? DASHBOARD_INTERVAL_MS : LOGS_INTERVAL_MS;
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    start(controller) {
      let closed = false;
      let ticking = false;

      const enqueue = (chunk: string) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(chunk));
        } catch {
          /* controller already closed */
        }
      };
      const send = (event: string, data: unknown) =>
        enqueue(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

      const tick = async () => {
        if (closed || ticking) return;
        ticking = true;
        try {
          let data: unknown;
          if (topic === 'logs') data = await logsPayload(searchParams);
          else if (topic === 'run') data = await runPayload(runId);
          else data = await dashboardPayload();
          send(topic, data);
        } catch (err) {
          send('error', { message: err instanceof Error ? err.message : String(err) });
        } finally {
          ticking = false;
        }
      };

      const cleanup = () => {
        if (closed) return;
        closed = true;
        clearInterval(dataTimer);
        clearInterval(heartbeatTimer);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      };

      enqueue(': connected\n\n');
      void tick();
      const dataTimer = setInterval(() => void tick(), intervalMs);
      const heartbeatTimer = setInterval(() => enqueue(': ping\n\n'), HEARTBEAT_MS);
      request.signal.addEventListener('abort', cleanup);
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
