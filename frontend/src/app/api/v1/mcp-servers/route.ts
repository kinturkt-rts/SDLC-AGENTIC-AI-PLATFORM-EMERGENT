import { NextResponse } from 'next/server';
import { listMcpServersFromCatalog } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const servers = await listMcpServersFromCatalog();
  return NextResponse.json({ servers });
}
