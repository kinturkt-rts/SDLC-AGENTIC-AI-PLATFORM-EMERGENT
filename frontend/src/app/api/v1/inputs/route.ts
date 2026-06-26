import { promises as fs } from 'fs';
import path from 'path';
import { NextResponse } from 'next/server';
import { getBackendRoot } from '@/src/lib/repo-root';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;
const MAX_BYTES = 256 * 1024;

interface SaveInputBody {
  feature?: unknown;
  content?: unknown;
  filename?: unknown;
}

function bad(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

export async function POST(request: Request) {
  let body: SaveInputBody;
  try {
    body = (await request.json()) as SaveInputBody;
  } catch {
    return bad('Body must be JSON: { feature, content }');
  }

  const feature = typeof body.feature === 'string' ? body.feature.trim().toLowerCase() : '';
  const content = typeof body.content === 'string' ? body.content : '';

  if (!feature) return bad('feature is required');
  if (!SLUG_RE.test(feature)) {
    return bad('feature must be lowercase letters, digits, dashes; start with a letter; <=64 chars');
  }
  if (!content.trim()) return bad('content is empty');

  const byteLen = Buffer.byteLength(content, 'utf-8');
  if (byteLen > MAX_BYTES) return bad(`content too large (${byteLen} bytes; limit ${MAX_BYTES})`, 413);

  const repoRoot = getBackendRoot();
  const inputsDir = path.join(repoRoot, 'inputs');
  await fs.mkdir(inputsDir, { recursive: true });

  const filename = `${feature}.txt`;
  const target = path.join(inputsDir, filename);
  const normalized = path.resolve(target);
  if (!normalized.startsWith(path.resolve(inputsDir) + path.sep)) {
    return bad('invalid feature path');
  }

  await fs.writeFile(target, content, 'utf-8');

  return NextResponse.json({
    feature,
    inputPath: `inputs/${filename}`,
    bytes: byteLen,
    savedAt: new Date().toISOString(),
  });
}
