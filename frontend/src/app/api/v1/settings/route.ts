import { NextResponse } from 'next/server';
import { getPlatformSettings } from '@/src/lib/platform-settings';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const settings = await getPlatformSettings();
  return NextResponse.json(settings);
}
