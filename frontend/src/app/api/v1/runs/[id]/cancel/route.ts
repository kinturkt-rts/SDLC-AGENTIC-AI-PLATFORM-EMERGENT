import { NextResponse } from 'next/server';
import { cancelPipelineRun } from '@/src/lib/cancel-run';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  try {
    const result = await cancelPipelineRun(params.id);
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const status = /not found/i.test(message)
      ? 404
      : /already (completed|failed|cancelled)/i.test(message)
        ? 409
        : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
