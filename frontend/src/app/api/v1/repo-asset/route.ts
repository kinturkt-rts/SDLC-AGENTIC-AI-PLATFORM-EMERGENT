import { NextResponse } from 'next/server';
import { readRepoAsset } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const filePath = searchParams.get('path');
  if (!filePath) {
    return NextResponse.json({ error: 'path query parameter required' }, { status: 400 });
  }

  const asset = await readRepoAsset(filePath);
  if (!asset) {
    return NextResponse.json({ error: 'File not found' }, { status: 404 });
  }

  return new NextResponse(asset.buffer, {
    headers: {
      'Content-Type': asset.contentType,
      'Cache-Control': 'private, max-age=60',
    },
  });
}
