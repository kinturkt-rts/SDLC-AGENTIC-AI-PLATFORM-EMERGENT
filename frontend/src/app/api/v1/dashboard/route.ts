import { NextResponse } from 'next/server';
import { getDashboardSummary } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const summary = await getDashboardSummary();
  return NextResponse.json(summary);
}
