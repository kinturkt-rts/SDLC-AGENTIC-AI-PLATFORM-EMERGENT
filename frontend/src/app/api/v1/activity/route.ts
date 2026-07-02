import { NextResponse } from 'next/server';
import { listRecentActivity } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';

export async function GET() {
  const activity = await listRecentActivity(8);
  return NextResponse.json({ activity });
}
