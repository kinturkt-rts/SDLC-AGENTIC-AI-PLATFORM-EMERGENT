import { NextResponse } from 'next/server';
import { listAgentMessages } from '@/src/lib/repo-reader';
import { apiRouteErrorResponse } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const correlationId = searchParams.get('correlationId') ?? undefined;
    const messages = await listAgentMessages(correlationId || undefined);
    return NextResponse.json({ messages });
  } catch (err) {
    return apiRouteErrorResponse(err);
  }
}
