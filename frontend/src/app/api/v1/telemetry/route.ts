import { NextRequest, NextResponse } from 'next/server';
import { getPipelineTelemetry } from '@/src/lib/pipeline-telemetry';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const project = request.nextUrl.searchParams.get('project')?.trim();
  if (!project) {
    return NextResponse.json({ error: 'project query parameter is required' }, { status: 400 });
  }

  try {
    const telemetry = await getPipelineTelemetry(project);
    return NextResponse.json(telemetry);
  } catch (err) {
    console.error('[telemetry]', err);
    return NextResponse.json({ error: 'Failed to load pipeline telemetry' }, { status: 500 });
  }
}
