import { NextResponse } from 'next/server';
import { loadBackendEnv } from '@/src/lib/backend-env';
import { submitBrief, validateTargetApp } from '@/src/lib/pipeline-run';

function formatSubmitError(err: unknown): string {
  loadBackendEnv();
  const message = err instanceof Error ? err.message : String(err);
  if (/SSO session associated with this profile has expired/i.test(message)) {
    const profile = process.env.AWS_PROFILE?.trim() || 'your-aws-profile';
    return `AWS SSO session expired for profile "${profile}". Run: aws sso login --profile ${profile}, then retry.`;
  }
  if (/timed out/i.test(message)) {
    return `${message}. If using S3, run: aws sso login --profile ${process.env.AWS_PROFILE?.trim() || 'your-aws-profile'}`;
  }
  return message;
}

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const MAX_BYTES = 256 * 1024;

interface SubmitBody {
  targetApp?: unknown;
  feature?: unknown;
  content?: unknown;
}

function bad(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

/**
 * Single submission: always allocates a new runId, uploads
 * runs/<runId>/inputs/<targetApp>.txt, then starts the orchestrator.
 */
export async function POST(request: Request) {
  loadBackendEnv();
  let body: SubmitBody;
  try {
    body = (await request.json()) as SubmitBody;
  } catch {
    return bad('Body must be JSON: { targetApp, content }');
  }

  const featureRaw =
    typeof body.targetApp === 'string'
      ? body.targetApp
      : typeof body.feature === 'string'
        ? body.feature
        : '';
  const content = typeof body.content === 'string' ? body.content : '';

  const slugError = validateTargetApp(featureRaw);
  if (slugError) return bad(slugError);
  if (!content.trim()) return bad('content is empty');
  if (Buffer.byteLength(content, 'utf-8') > MAX_BYTES) {
    return bad(`content too large (limit ${MAX_BYTES})`, 413);
  }

  try {
    const result = await submitBrief(featureRaw, content);
    return NextResponse.json({
      ...result,
      feature: result.targetApp,
      inputPath: result.inputFile,
      submittedAt: new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json({ error: formatSubmitError(err) }, { status: 500 });
  }
}
