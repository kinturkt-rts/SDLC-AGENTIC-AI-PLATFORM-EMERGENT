import { NextResponse } from 'next/server';
import { getRun } from '@/src/lib/repo-reader';
import { getRunHandoffs } from '@/src/lib/pipeline-handoffs';
import { buildRunAgentMessages } from '@/src/lib/agent-messages';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: Request) {
  const runId = new URL(request.url).searchParams.get('runId')?.trim();
  if (!runId) {
    return NextResponse.json({ error: 'runId query parameter is required' }, { status: 400 });
  }

  const run = await getRun(runId);
  if (!run) {
    return NextResponse.json({ error: 'Run not found' }, { status: 404 });
  }

  const handoffs = await getRunHandoffs(run.id, run.projectId).catch(() => null);
  const messages = buildRunAgentMessages(run, handoffs);
  return NextResponse.json({ messages });
}
