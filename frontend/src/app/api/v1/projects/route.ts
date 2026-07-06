import { NextResponse } from 'next/server';
import { listProjects } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const projects = await listProjects();
    return NextResponse.json({ projects });
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
