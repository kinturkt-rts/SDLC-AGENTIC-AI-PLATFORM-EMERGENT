import { NextResponse } from 'next/server';
import { readConfig, writeConfig, validateServer } from '@/src/lib/mcp-store';
import type { McpServerConfig } from '@/src/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// GET /api/mcp -> full mcp.json
export async function GET() {
  const config = await readConfig();
  return NextResponse.json(config);
}

// POST /api/mcp -> add or update one server entry. Body: { name, config }
export async function POST(request: Request) {
  let body: { name?: string; config?: McpServerConfig };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const name = (body.name ?? '').trim();
  const config = body.config ?? {};
  const validation = validateServer(name, config);
  if (!validation.valid) {
    return NextResponse.json({ error: 'Validation failed', errors: validation.errors }, { status: 400 });
  }

  const current = await readConfig();
  current.mcpServers[name] = config;
  await writeConfig(current);
  return NextResponse.json({ ok: true, name, mcpServers: current.mcpServers });
}
