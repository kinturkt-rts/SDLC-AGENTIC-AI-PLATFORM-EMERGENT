import { NextResponse } from 'next/server';
import { listContextItems } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectSlug = searchParams.get('projectSlug') ?? undefined;
  const items = await listContextItems(projectSlug);
  return NextResponse.json({ items });
}
