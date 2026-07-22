import { NextResponse } from 'next/server';
import { listRuns } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const runs = await listRuns();
    return NextResponse.json(
      { runs },
      {
        headers: {
          'Cache-Control': 'no-store, no-cache, must-revalidate',
        },
      },
    );
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
