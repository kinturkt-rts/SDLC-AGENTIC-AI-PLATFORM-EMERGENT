import path from 'path';

/** Monorepo root (parent of frontend/). */
export function getMonorepoRoot(): string {
  return path.resolve(process.cwd(), '..');
}

/**
 * Backend data root: agents/, docs/, inputs/, target-apps/, orchestrator/, etc.
 * Override with BACKEND_ROOT or REPO_ROOT in frontend/.env.local if needed.
 */
export function getBackendRoot(): string {
  const override = process.env.BACKEND_ROOT?.trim() || process.env.REPO_ROOT?.trim();
  if (override) return path.resolve(override);
  return path.join(getMonorepoRoot(), 'backend');
}

/** @deprecated Use getBackendRoot — kept for call-site compatibility. */
export function getRepoRoot(): string {
  return getBackendRoot();
}
