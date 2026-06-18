import { NextResponse } from 'next/server';
import { mockProjects } from '@/src/mocks';

// Future-ready stub. Returns the project registry in the same shape the UI consumes.
// When the real backend exists, this reads discovered projects from
// agents/pipeline/<slug>.context.json instead of the mock registry.
export async function GET() {
  const projects = mockProjects.map((p) => ({
    id: p.id,
    name: p.name,
    slug: p.slug,
    description: p.description,
    pipelineStatus: p.pipelineStatus,
    artifactCount: p.artifactCount,
    lastRunAt: p.lastRunAt,
    repo: p.repo,
  }));
  return NextResponse.json({ projects });
}
