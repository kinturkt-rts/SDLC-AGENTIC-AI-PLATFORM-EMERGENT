import { NextResponse } from 'next/server';
import { listPipelineLogs } from '@/src/lib/repo-reader';
import type { AgentName } from '@/src/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const KNOWN_AGENTS = new Set<string>([
  'orchestrator-agent',
  'product-agent',
  'architect-agent',
  'database-agent',
  'developer-agent',
  'gitlab-agent',
  'qa-agent',
  'devops-agent',
  'security-agent',
]);

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get('runId')?.trim() || undefined;
  const agentRaw = searchParams.get('agent')?.trim();
  const agent =
    agentRaw && KNOWN_AGENTS.has(agentRaw) ? (agentRaw as AgentName) : undefined;

  const minutesRaw = searchParams.get('minutes');
  let minutes: number | undefined;
  if (minutesRaw) {
    const parsed = Number.parseInt(minutesRaw, 10);
    if (Number.isFinite(parsed) && parsed > 0) minutes = parsed;
  }

  const logs = await listPipelineLogs({ runId, agent, minutes });
  return NextResponse.json({ logs, source: 'pipeline' });
}
