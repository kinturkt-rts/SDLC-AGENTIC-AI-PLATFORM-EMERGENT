import { NextResponse } from 'next/server';
import { listProjects } from '@/src/lib/repo-reader';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const projects = await listProjects();
  return NextResponse.json({ projects });
}
