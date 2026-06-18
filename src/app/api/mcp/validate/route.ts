import { NextResponse } from 'next/server';
import { validateServer } from '@/src/lib/mcp-store';
import type { McpServerConfig } from '@/src/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// POST /api/mcp/validate -> validate a server entry shape. Body: { name, config }
export async function POST(request: Request) {
  let body: { name?: string; config?: McpServerConfig };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ valid: false, errors: ['Invalid JSON body'] }, { status: 400 });
  }
  const result = validateServer((body.name ?? '').trim(), body.config ?? {});
  return NextResponse.json(result);
}
