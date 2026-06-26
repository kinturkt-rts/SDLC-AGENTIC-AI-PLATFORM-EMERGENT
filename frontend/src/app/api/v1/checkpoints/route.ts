import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/** HITL checkpoints are not persisted in the monorepo yet. */
export async function GET() {
  return NextResponse.json({ checkpoints: [] });
}
