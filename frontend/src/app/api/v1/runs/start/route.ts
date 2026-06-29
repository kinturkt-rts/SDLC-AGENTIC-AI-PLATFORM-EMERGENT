import { NextResponse } from 'next/server';
import { startPipeline, validateTargetApp } from '@/src/lib/pipeline-run';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

interface StartBody {
  feature?: unknown;
  targetApp?: unknown;
  runId?: unknown;
  inputPath?: unknown;
  inputFile?: unknown;
}

function bad(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

export async function POST(request: Request) {
  let body: StartBody;
  try {
    body = (await request.json()) as StartBody;
  } catch {
    return bad('Body must be JSON: { targetApp, runId, inputFile }');
  }

  const featureRaw =
    typeof body.targetApp === 'string'
      ? body.targetApp
      : typeof body.feature === 'string'
        ? body.feature
        : '';
  const runId = typeof body.runId === 'string' ? body.runId.trim() : '';
  const inputFile =
    (typeof body.inputFile === 'string' && body.inputFile.trim()) ||
    (typeof body.inputPath === 'string' && body.inputPath.trim()) ||
    '';

  const slugError = validateTargetApp(featureRaw);
  if (slugError) return bad(slugError);
  if (!runId) return bad('runId is required');
  if (!inputFile) return bad('inputFile is required');

  try {
    const result = await startPipeline({
      targetApp: featureRaw,
      runId,
      inputFile,
    });
    return NextResponse.json({
      ...result,
      feature: result.targetApp,
      inputPath: result.inputFile,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const status = message.includes('not found') ? 404 : message.includes('spawn') ? 500 : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
