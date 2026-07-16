import { NextResponse } from 'next/server';
import { listArtifacts } from '@/src/lib/repo-reader';
import { artifactMatchesKind } from '@/src/lib/artifact-kinds';
import type { ArtifactKind } from '@/src/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get('project')?.trim() || null;
  const kindParam = searchParams.get('kind')?.trim() || 'all';
  const kind = (kindParam || 'all') as ArtifactKind | 'all';

  let artifacts = await listArtifacts();
  if (project) {
    artifacts = artifacts.filter((a) => a.projectId === project);
  }
  if (kind !== 'all') {
    artifacts = artifacts.filter((a) => artifactMatchesKind(a, kind));
  }

  return NextResponse.json(
    { artifacts },
    {
      headers: {
        'Cache-Control': 'no-store, max-age=0',
      },
    },
  );
}
