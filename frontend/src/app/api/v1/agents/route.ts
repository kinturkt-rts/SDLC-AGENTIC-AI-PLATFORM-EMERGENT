import { NextResponse } from 'next/server';
import { listAgents } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const agents = await listAgents();
    return NextResponse.json({ agents });
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
