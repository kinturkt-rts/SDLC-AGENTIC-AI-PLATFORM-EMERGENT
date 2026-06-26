import { NextResponse } from 'next/server';
import { listPipelines } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const pipelines = await listPipelines();
  return NextResponse.json({ pipelines });
}
