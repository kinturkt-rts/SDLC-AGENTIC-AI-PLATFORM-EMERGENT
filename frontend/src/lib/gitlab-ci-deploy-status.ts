/**
 * Poll GitLab for the latest CI pipeline on an apps-repo branch so the control
 * plane can mark Deploy failed when CI fails (no devops.json / appUrl written).
 */
import { loadBackendEnv } from './backend-env';

export type GitlabPipelineDeployStatus =
  | 'running'
  | 'success'
  | 'failed'
  | 'canceled'
  | 'unknown'
  | 'unavailable';

type CacheEntry = { at: number; status: GitlabPipelineDeployStatus; webUrl?: string | null };

const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 15_000;

function gitlabApiBase(): string {
  loadBackendEnv();
  const raw =
    process.env.GITLAB_API_URL?.trim() ||
    process.env.GITLAB_URL?.trim() ||
    'https://code.junodev.net';
  return raw.replace(/\/$/, '').replace(/\/api\/v4$/i, '') + '/api/v4';
}

function gitlabToken(): string {
  loadBackendEnv();
  return (
    process.env.GITLAB_PERSONAL_ACCESS_TOKEN?.trim() ||
    process.env.GITLAB_TOKEN?.trim() ||
    ''
  );
}

/** Map GitLab pipeline status → coarse deploy signal for the UI. */
export function mapGitlabPipelineStatus(raw: string | null | undefined): GitlabPipelineDeployStatus {
  const s = (raw ?? '').trim().toLowerCase();
  if (!s) return 'unknown';
  if (s === 'success' || s === 'manual') return 'success';
  if (s === 'failed' || s === 'canceled' || s === 'cancelled') return 'failed';
  if (
    s === 'running' ||
    s === 'pending' ||
    s === 'created' ||
    s === 'waiting_for_resource' ||
    s === 'preparing' ||
    s === 'scheduled'
  ) {
    return 'running';
  }
  if (s === 'skipped') return 'unknown';
  return 'unknown';
}

/**
 * Latest pipeline status for project + branch (e.g. sdlc/bike-locker-reservation).
 * Cached briefly to avoid hammering GitLab while the dashboard polls.
 */
export async function getLatestGitlabPipelineDeployStatus(options: {
  gitlabProject: string;
  branch: string;
}): Promise<{ status: GitlabPipelineDeployStatus; webUrl: string | null }> {
  const project = options.gitlabProject.trim();
  const branch = options.branch.trim();
  if (!project || !branch) {
    return { status: 'unavailable', webUrl: null };
  }

  const cacheKey = `${project}|${branch}`;
  const hit = cache.get(cacheKey);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) {
    return { status: hit.status, webUrl: hit.webUrl ?? null };
  }

  const token = gitlabToken();
  if (!token) {
    const miss = { status: 'unavailable' as const, webUrl: null };
    cache.set(cacheKey, { at: Date.now(), ...miss });
    return miss;
  }

  const api = gitlabApiBase();
  const projectEnc = encodeURIComponent(project);
  const refEnc = encodeURIComponent(branch);
  const url = `${api}/projects/${projectEnc}/pipelines?ref=${refEnc}&per_page=1`;

  try {
    const res = await fetch(url, {
      headers: { 'PRIVATE-TOKEN': token },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(8_000),
    });
    if (!res.ok) {
      const miss = { status: 'unavailable' as const, webUrl: null };
      cache.set(cacheKey, { at: Date.now(), ...miss });
      return miss;
    }
    const rows = (await res.json()) as Array<{ status?: string; web_url?: string }>;
    const top = Array.isArray(rows) && rows.length > 0 ? rows[0] : null;
    const status = mapGitlabPipelineStatus(top?.status);
    const webUrl = typeof top?.web_url === 'string' ? top.web_url : null;
    cache.set(cacheKey, { at: Date.now(), status, webUrl });
    return { status, webUrl };
  } catch {
    const miss = { status: 'unavailable' as const, webUrl: null };
    cache.set(cacheKey, { at: Date.now(), ...miss });
    return miss;
  }
}