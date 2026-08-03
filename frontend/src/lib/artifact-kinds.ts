import type { Artifact, ArtifactKind } from '@/src/types';

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

/**
 * Filter options shown on the Artifacts page.
 * Deliverables review surface, not a file browser - SQL, code, tests, and config
 * are intentionally excluded from every user of this platform, not just hidden by default.
 */
export const ARTIFACT_FILTER_KINDS: ArtifactKind[] = ['prd', 'architecture', 'diagram'];

const ARTIFACT_FILTER_KIND_SET = new Set<ArtifactKind>(ARTIFACT_FILTER_KINDS);

/** True when this artifact's kind belongs on the Artifacts page at all (any filter, including "all"). */
export function isVisibleArtifactKind(kind: ArtifactKind): boolean {
  return ARTIFACT_FILTER_KIND_SET.has(kind);
}

export function artifactKindLabel(kind: ArtifactKind): string {
  return ARTIFACT_KIND_LABELS[kind] ?? kind;
}

/** Strict path checks so mis-tagged rows never leak into Kind filters. */
export function artifactMatchesKind(artifact: Artifact, kind: ArtifactKind | 'all'): boolean {
  if (kind === 'all') return isVisibleArtifactKind(artifact.kind);

  const lower = artifact.path.replace(/\\/g, '/').toLowerCase();
  const isCodeLike =
    lower.endsWith('.py') ||
    lower.endsWith('.ts') ||
    lower.endsWith('.tsx') ||
    lower.endsWith('.js') ||
    lower.endsWith('.jsx') ||
    lower.endsWith('requirements.txt') ||
    lower.includes('/app/') ||
    lower.includes('/ui/') ||
    lower.includes('/tests/');

  const norm = lower.replace(/^\/+/, '');
  switch (kind) {
    case 'prd':
      return (
        !isCodeLike &&
        (artifact.kind === 'prd' ||
          norm.startsWith('docs/prd/') ||
          norm.includes('/docs/prd/') ||
          norm.includes('/prd/') ||
          /(^|\/)prd\.md$/.test(norm))
      );
    case 'architecture':
      return (
        !isCodeLike &&
        (artifact.kind === 'architecture' ||
          norm.startsWith('docs/design/') ||
          norm.includes('/docs/design/') ||
          ((norm.startsWith('design/') || norm.includes('/design/')) && norm.endsWith('.md')))
      );
    case 'diagram':
      return (
        artifact.kind === 'diagram' ||
        norm.startsWith('docs/generated-diagrams/') ||
        norm.includes('/docs/generated-diagrams/') ||
        norm.startsWith('docs/diagrams/') ||
        norm.includes('/docs/diagrams/') ||
        norm.endsWith('.png') ||
        norm.endsWith('.svg') ||
        norm.endsWith('.jpg') ||
        norm.endsWith('.jpeg')
      );
    case 'migration':
      return (
        artifact.kind === 'migration' ||
        (norm.endsWith('.sql') &&
          (norm.startsWith('db/sql/') || norm.includes('/db/sql/') || norm.includes('/sql/')))
      );
    case 'code':
      return artifact.kind === 'code' || isCodeLike;
    default:
      return artifact.kind === kind;
  }
}
