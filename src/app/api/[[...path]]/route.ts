import { NextResponse } from 'next/server';

// The control plane is read-only and serves the UI from a typed mock layer.
// This route exists only for health checks; the real platform API lives at
// NEXT_PUBLIC_API_BASE_URL and is consumed client-side via src/lib/api.ts.

function cors(res: NextResponse) {
  res.headers.set('Access-Control-Allow-Origin', process.env.CORS_ORIGINS || '*');
  res.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  return res;
}

export async function OPTIONS() {
  return cors(new NextResponse(null, { status: 200 }));
}

async function handler(_request: Request, { params }: { params: { path?: string[] } }) {
  const route = `/${(params.path ?? []).join('/')}`;
  if (route === '/' || route === '/health') {
    return cors(
      NextResponse.json({
        service: 'helmsman-control-plane',
        status: 'ok',
        mode: process.env.NEXT_PUBLIC_API_BASE_URL ? 'live' : 'mock',
        time: new Date().toISOString(),
      }),
    );
  }
  return cors(NextResponse.json({ error: `Route ${route} not found` }, { status: 404 }));
}

export const GET = handler;
export const POST = handler;
