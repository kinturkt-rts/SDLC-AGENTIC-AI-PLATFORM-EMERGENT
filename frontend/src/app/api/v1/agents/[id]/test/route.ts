import { NextResponse } from 'next/server';
import { invokeAgentRuntimeA2a, loadAgentRuntimeMeta } from '@/src/lib/agentcore-invoke';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const HEALTH_CHECK_MESSAGE =
  'Control-plane health check only. Do not run tools or start SDLC tasks. Reply with exactly: OK';

export async function POST(_request: Request, { params }: { params: { id: string } }) {
  const agentId = params.id?.trim();
  if (!agentId) {
    return NextResponse.json({ error: 'Agent id is required' }, { status: 400 });
  }

  try {
    const meta = await loadAgentRuntimeMeta(agentId);
    if (!meta.deployed) {
      return NextResponse.json(
        {
          status: 'error',
          agentName: agentId,
          error: `${agentId} is not deployed to AgentCore (see config/agentcore/runtimes.json)`,
        },
        { status: 422 },
      );
    }

    const started = Date.now();
    const result = await invokeAgentRuntimeA2a(agentId, HEALTH_CHECK_MESSAGE, { timeoutSec: 120 });
    const latencyMs = Date.now() - started;

    return NextResponse.json({
      ...result,
      latencyMs,
      healthCheck: true,
    });
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
