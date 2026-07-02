import { NextResponse } from 'next/server';
import { getRun } from '@/src/lib/repo-reader';
import { getRunHandoffs } from '@/src/lib/pipeline-handoffs';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const run = await getRun(params.id);
  if (!run) {
    return NextResponse.json({ error: 'Run not found' }, { status: 404 });
  }

  const handoffs = await getRunHandoffs(run.id, run.projectId);
  return NextResponse.json(handoffs);
}
