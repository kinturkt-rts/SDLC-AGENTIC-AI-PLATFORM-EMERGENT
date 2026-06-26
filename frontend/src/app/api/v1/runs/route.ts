import { NextResponse } from 'next/server';
import { listRuns } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const runs = await listRuns();
  return NextResponse.json({ runs });
}
