import { NextResponse } from 'next/server';
import { getAgent } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const agent = await getAgent(params.id);
  if (!agent) {
    return NextResponse.json({ error: 'Agent not found' }, { status: 404 });
  }
  return NextResponse.json(agent);
}
