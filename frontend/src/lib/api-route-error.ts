import { NextResponse } from 'next/server';
import { loadBackendEnv } from './backend-env';

export function formatApiRouteError(err: unknown): string {
  loadBackendEnv();
  const message = err instanceof Error ? err.message : String(err);
  if (/SSO session associated with this profile has expired/i.test(message)) {
    const profile = process.env.AWS_PROFILE?.trim() || 'your-aws-profile';
    return `AWS SSO session expired for profile "${profile}". Run: aws sso login --profile ${profile}, then restart npm run dev.`;
  }
  if (/TimeoutError|timed out|ECONNRESET|ENOTFOUND/i.test(message)) {
    const profile = process.env.AWS_PROFILE?.trim() || 'your-aws-profile';
    return (
      `${message}. This usually means AWS SSO expired or the dev server is busy. ` +
      `Run: aws sso login --profile ${profile}, restart npm run dev, then retry Submit.`
    );
  }
  return message;
}

export function apiRouteErrorResponse(err: unknown, status = 503): NextResponse {
  return NextResponse.json({ error: formatApiRouteError(err) }, { status });
}
