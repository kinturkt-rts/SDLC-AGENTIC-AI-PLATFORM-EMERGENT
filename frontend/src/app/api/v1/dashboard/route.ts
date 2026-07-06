import { NextResponse } from 'next/server';
import { getDashboardSummary } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const summary = await getDashboardSummary();
    return NextResponse.json(summary);
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
