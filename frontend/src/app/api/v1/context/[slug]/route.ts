import { NextResponse } from 'next/server';
import { getPipelineContext } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: Request, { params }: { params: { slug: string } }) {
  const context = await getPipelineContext(params.slug);
  if (!context) {
    return NextResponse.json({ error: 'Pipeline context not found' }, { status: 404 });
  }
  return NextResponse.json(context);
}
