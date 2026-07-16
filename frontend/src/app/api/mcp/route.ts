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
// Partial updates merge into the existing entry (e.g. toggle sends { disabled }).
export async function POST(request: Request) {
  let body: { name?: string; config?: McpServerConfig };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const name = (body.name ?? '').trim();
  const patch = body.config ?? {};
  const current = await readConfig();
  const existing = current.mcpServers[name];
  const merged: McpServerConfig = existing ? { ...existing, ...patch } : patch;

  const patchKeys = Object.keys(patch);
  const disabledOnly =
    !!existing && patchKeys.length === 1 && patchKeys[0] === 'disabled' && typeof patch.disabled === 'boolean';

  if (!disabledOnly) {
    const validation = validateServer(name, merged);
    if (!validation.valid) {
      return NextResponse.json({ error: 'Validation failed', errors: validation.errors }, { status: 400 });
    }
  }

  current.mcpServers[name] = merged;
  await writeConfig(current);
  return NextResponse.json({ ok: true, name, mcpServers: current.mcpServers });
}
