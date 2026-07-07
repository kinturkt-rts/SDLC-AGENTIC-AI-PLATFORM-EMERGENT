import { NextResponse } from 'next/server';
import { listRunLogs } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const logs = await listRunLogs(params.id);
  return NextResponse.json({ logs, source: 'run', runId: params.id });
}
