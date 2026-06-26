import { NextResponse } from 'next/server';
import { readConfig, writeConfig } from '@/src/lib/mcp-store';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// DELETE /api/mcp/[name] -> remove a server entry by key
export async function DELETE(_request: Request, { params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name);
  const current = await readConfig();
  if (!(name in current.mcpServers)) {
    return NextResponse.json({ error: `Server '${name}' not found` }, { status: 404 });
  }
  delete current.mcpServers[name];
  await writeConfig(current);
  return NextResponse.json({ ok: true, name, mcpServers: current.mcpServers });
}
