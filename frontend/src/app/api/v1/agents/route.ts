import { NextResponse } from 'next/server';
import { listAgents } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const agents = await listAgents();
  return NextResponse.json({ agents });
}
