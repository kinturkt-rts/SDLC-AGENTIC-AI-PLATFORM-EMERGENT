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
  withJira?: unknown;
  jiraProject?: unknown;
  triggeredBy?: unknown;
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
  const withJira = body.withJira === true || body.withJira === 'true';
  const jiraProject = typeof body.jiraProject === 'string' ? body.jiraProject.trim().toUpperCase() : '';
  const triggeredBy = typeof body.triggeredBy === 'string' ? body.triggeredBy.trim() : '';

  const slugError = validateTargetApp(featureRaw);
  if (slugError) return bad(slugError);
  if (!runId) return bad('runId is required');
  if (!inputFile) return bad('inputFile is required');
  if (withJira && !jiraProject) return bad('jiraProject is required when withJira is true');

  try {
    const result = await startPipeline({
      targetApp: featureRaw,
      runId,
      inputFile,
      withJira,
      jiraProject: withJira ? jiraProject : undefined,
      triggeredBy: triggeredBy || undefined,
    });
    return NextResponse.json({
      ...result,
      feature: result.targetApp,
      inputPath: result.inputFile,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    const status = message.includes('not found')
      ? 404
      : /already has an active pipeline|Maximum concurrent runs/i.test(message)
        ? 409
        : message.includes('spawn')
          ? 500
          : 400;
    return NextResponse.json({ error: message }, { status });
  }
}
