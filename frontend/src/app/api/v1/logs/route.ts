import { NextResponse } from 'next/server';
import { listCloudWatchLogs } from '@/src/lib/cloudwatch-logs';
import { parseLogAgentQuery } from '@/src/lib/pipeline-phases';
import { listPipelineLogs } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

type LogSource = 'local' | 'cloudwatch';

function resolveSource(value: string | null | undefined): LogSource {
  if (value === 'cloudwatch') return 'cloudwatch';
  return 'local';
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const source = resolveSource(searchParams.get('source'));
  const runId = searchParams.get('runId')?.trim() || undefined;
  const agent = parseLogAgentQuery(searchParams.get('agent'));

  const minutesRaw = searchParams.get('minutes');
  let minutes: number | undefined;
  if (minutesRaw) {
    const parsed = Number.parseInt(minutesRaw, 10);
    if (Number.isFinite(parsed) && parsed > 0) minutes = parsed;
  }

  const limitRaw = searchParams.get('limit');
  let limit: number | undefined;
  if (limitRaw) {
    const parsed = Number.parseInt(limitRaw, 10);
    if (Number.isFinite(parsed) && parsed > 0) limit = parsed;
  }

  if (source === 'cloudwatch') {
    const logs = await listCloudWatchLogs({ runId, agent, minutes, limit });
    return NextResponse.json({ logs, source: 'cloudwatch' });
  }

  const logs = await listPipelineLogs({ runId, agent, minutes, limit });
  return NextResponse.json({ logs, source: 'pipeline' });
}
