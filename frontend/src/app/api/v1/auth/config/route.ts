import { NextResponse } from 'next/server';
import { getCognitoPublicConfig } from '@/src/lib/cognito-config';

/** Must read ECS/runtime env — never bake Cognito IDs at image build time. */
export const dynamic = 'force-dynamic';

/** Public Cognito IDs for the browser Amplify client (no secrets). */
export async function GET() {
  const config = getCognitoPublicConfig();
  return NextResponse.json(config, {
    headers: { 'Cache-Control': 'no-store' },
  });
}
