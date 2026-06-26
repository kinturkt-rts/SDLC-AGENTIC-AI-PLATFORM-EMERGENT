import { NextResponse } from 'next/server';
import { listRunEvents } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const events = await listRunEvents(params.id);
  return NextResponse.json({ events });
}
