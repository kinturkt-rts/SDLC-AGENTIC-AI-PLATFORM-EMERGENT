import { NextResponse } from 'next/server';
import { getTelemetryOverview } from '@/src/lib/pipeline-telemetry';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const projects = await getTelemetryOverview();
    return NextResponse.json({ projects });
  } catch (err) {
    console.error('[telemetry/overview]', err);
    return NextResponse.json({ error: 'Failed to load telemetry overview' }, { status: 500 });
  }
}
