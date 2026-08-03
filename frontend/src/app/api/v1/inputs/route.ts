import { NextResponse } from 'next/server';
import { uploadBrief, validateTargetApp } from '@/src/lib/pipeline-run';
import { readInputBrief } from '@/src/lib/repo-reader';
import { formatApiRouteError } from '@/src/lib/api-route-error';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const MAX_BYTES = 256 * 1024;

interface SaveInputBody {
  feature?: unknown;
  targetApp?: unknown;
  content?: unknown;
  runId?: unknown;
}

function bad(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const slug = (url.searchParams.get('slug') || url.searchParams.get('project') || '').trim();
  const runId = url.searchParams.get('runId')?.trim() || undefined;
  if (!slug) return bad('slug (or project) query parameter is required');

  try {
    const brief = await readInputBrief(slug, runId);
    if (!brief) return NextResponse.json({ error: 'Brief not found' }, { status: 404 });
    return NextResponse.json(brief);
  } catch (err) {
    return NextResponse.json({ error: formatApiRouteError(err) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  let body: SaveInputBody;
  try {
    body = (await request.json()) as SaveInputBody;
  } catch {
    return bad('Body must be JSON: { targetApp|feature, content, runId? }');
  }

  const featureRaw =
    typeof body.targetApp === 'string'
      ? body.targetApp
      : typeof body.feature === 'string'
        ? body.feature
        : '';
  const content = typeof body.content === 'string' ? body.content : '';
  const runId = typeof body.runId === 'string' ? body.runId.trim() : undefined;

  const slugError = validateTargetApp(featureRaw);
  if (slugError) return bad(slugError);
  if (!content.trim()) return bad('content is empty');
  if (Buffer.byteLength(content, 'utf-8') > MAX_BYTES) {
    return bad(`content too large (limit ${MAX_BYTES})`, 413);
  }

  try {
    const result = await uploadBrief(featureRaw, content, runId);
    return NextResponse.json({
      ...result,
      feature: result.targetApp,
      inputPath: result.inputFile,
      savedAt: new Date().toISOString(),
    });
  } catch (err) {
    const message = formatApiRouteError(err);
    const status = /S3|AWS|timed out|SSO/i.test(message) ? 503 : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
