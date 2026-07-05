import { NextResponse } from 'next/server';
import { listProjects } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  try {
    const projects = await listProjects();
    return NextResponse.json({ projects });
  } catch (err) {
    console.error('[projects]', err);
    return NextResponse.json({ error: 'Failed to load projects' }, { status: 500 });
  }
}
