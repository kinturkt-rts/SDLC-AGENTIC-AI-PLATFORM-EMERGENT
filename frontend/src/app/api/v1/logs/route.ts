import { NextResponse } from 'next/server';
import { listCloudWatchLogs } from '@/src/lib/cloudwatch-logs';
import { parseLogAgentQuery } from '@/src/lib/pipeline-phases';
import { getRun } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function runLogTimeBounds(run: { startedAt: string; finishedAt?: string | null }) {
  const startMs = Date.parse(run.startedAt) - 2 * 60_000;
  const endMs = run.finishedAt ? Date.parse(run.finishedAt) + 5 * 60_000 : undefined;
  return { startMs, endMs };
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
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
      const { startMs, endMs } = runLogTimeBounds(run);
      const logs = await listCloudWatchLogs({
        runId,
        startMs,
        endMs,
        agent,
        limit,
        mvpOnly: true,
        timeWindowForRun: true,
      });
      return NextResponse.json({ logs, source: 'cloudwatch', runId });
    }
  }

  const logs = await listCloudWatchLogs({ agent, minutes: minutes ?? 240, limit, mvpOnly: true });
  return NextResponse.json({ logs, source: 'cloudwatch' });
}
