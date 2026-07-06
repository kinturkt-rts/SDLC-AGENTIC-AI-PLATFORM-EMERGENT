import { NextResponse } from 'next/server';
import { listRecentActivity } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const activity = await listRecentActivity(12);
    return NextResponse.json({ activity });
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
