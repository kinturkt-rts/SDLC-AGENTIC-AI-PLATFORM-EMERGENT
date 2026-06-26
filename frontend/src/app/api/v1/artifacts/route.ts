import { NextResponse } from 'next/server';
import { listArtifacts } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const artifacts = await listArtifacts();
  return NextResponse.json({ artifacts });
}
