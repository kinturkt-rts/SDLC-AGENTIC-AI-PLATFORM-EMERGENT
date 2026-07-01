import type { ArtifactKind } from '@/src/types';

/** Human-readable labels for artifact kinds (UI only). */
export const ARTIFACT_KIND_LABELS: Record<ArtifactKind, string> = {
  prd: 'PRD',
  architecture: 'Design Doc',
  diagram: 'Architecture Diagram',
  migration: 'SQL',
  code: 'Code',
  test: 'Test',
  scan: 'Scan',
  cicd: 'CI/CD',
  doc: 'Doc',
};

/** Filter options shown on the Artifacts page (MVP-first order). */
export const ARTIFACT_FILTER_KINDS: ArtifactKind[] = [
  'prd',
  'architecture',
  'diagram',
  'migration',
  'code',
  'cicd',
  'test',
  'scan',
];

export function artifactKindLabel(kind: ArtifactKind): string {
  return ARTIFACT_KIND_LABELS[kind] ?? kind;
}
