/**
 * Poll GitLab for CI pipelines on an apps-repo branch so the control plane can
 * sync Deploy UI with real deploy progress (not only success via appUrl).
 *
 * gitlab-agent publishes many rapid commits → many pipelines. Deploy jobs share
 * resource_group deploy-$CI_COMMIT_REF_SLUG, so most sit in waiting_for_resource
 * while one runs. Never treat "latest pipeline failed/canceled" as terminal if
 * any recent pipeline on the branch is still in flight.
 */
import { loadBackendEnv } from './backend-env';

export type GitlabPipelineDeployStatus =
  | 'running'
  | 'success'
  | 'failed'
  | 'canceled'
  | 'unknown'
  | 'unavailable';

export type GitlabBranchDeploySignal = {
  status: GitlabPipelineDeployStatus;
  webUrl: string | null;
  /** True when any recent pipeline is still queued or executing. */
  inFlight: boolean;
};

type CacheEntry = { at: number; signal: GitlabBranchDeploySignal };

const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 15_000;
/** How many recent pipelines to inspect (multi-commit publish floods the branch). */
const PIPELINES_PAGE_SIZE = 15;

type GitlabPipelineRow = {
  status?: string;
  web_url?: string;
  id?: number;
};

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
  if (s === 'failed') return 'failed';
  if (s === 'canceled' || s === 'cancelled') return 'canceled';
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

function isInFlightStatus(status: GitlabPipelineDeployStatus): boolean {
  return status === 'running';
}

/**
 * Aggregate recent pipelines on a branch into one deploy signal.
 * In-flight (running / waiting_for_resource / …) always wins over failed/canceled
 * so intermediate commits and resource_group queues do not flash Failed in the UI.
 */
export function aggregateGitlabBranchDeployStatus(
  rows: GitlabPipelineRow[],
): GitlabBranchDeploySignal {
  if (!Array.isArray(rows) || rows.length === 0) {
    return { status: 'unknown', webUrl: null, inFlight: false };
  }

  const mapped = rows.map((row) => ({
    status: mapGitlabPipelineStatus(row.status),
    webUrl: typeof row.web_url === 'string' ? row.web_url : null,
  }));

  const inFlight = mapped.find((m) => isInFlightStatus(m.status));
  if (inFlight) {
    return { status: 'running', webUrl: inFlight.webUrl, inFlight: true };
  }

  const latest = mapped[0];
  if (latest.status === 'success') {
    return { status: 'success', webUrl: latest.webUrl, inFlight: false };
  }
  if (latest.status === 'failed' || latest.status === 'canceled') {
    // Canceled waiting jobs after a failed attempt still mean deploy did not succeed.
    return { status: 'failed', webUrl: latest.webUrl, inFlight: false };
  }
  return { status: latest.status, webUrl: latest.webUrl, inFlight: false };
}

/**
 * Deploy signal for project + branch (e.g. sdlc/bike-locker-reservation).
 * Inspects several recent pipelines so resource_group queues and multi-commit
 * publishes do not produce false Failed. Cached briefly while the dashboard polls.
 */
export async function getGitlabBranchDeploySignal(options: {
  gitlabProject: string;
  branch: string;
}): Promise<GitlabBranchDeploySignal> {
  const project = options.gitlabProject.trim();
  const branch = options.branch.trim();
  if (!project || !branch) {
    return { status: 'unavailable', webUrl: null, inFlight: false };
  }

  const cacheKey = `${project}|${branch}`;
  const hit = cache.get(cacheKey);
  if (hit && Date.now() - hit.at < CACHE_TTL_MS) {
    return hit.signal;
  }

  const token = gitlabToken();
  if (!token) {
    const miss: GitlabBranchDeploySignal = {
      status: 'unavailable',
      webUrl: null,
      inFlight: false,
    };
    cache.set(cacheKey, { at: Date.now(), signal: miss });
    return miss;
  }

  const api = gitlabApiBase();
  const projectEnc = encodeURIComponent(project);
  const refEnc = encodeURIComponent(branch);
  const url = `${api}/projects/${projectEnc}/pipelines?ref=${refEnc}&per_page=${PIPELINES_PAGE_SIZE}`;

  try {
    const res = await fetch(url, {
      headers: { 'PRIVATE-TOKEN': token },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(8_000),
    });
    if (!res.ok) {
      const miss: GitlabBranchDeploySignal = {
        status: 'unavailable',
        webUrl: null,
        inFlight: false,
      };
      cache.set(cacheKey, { at: Date.now(), signal: miss });
      return miss;
    }
    const rows = (await res.json()) as GitlabPipelineRow[];
    const signal = aggregateGitlabBranchDeployStatus(Array.isArray(rows) ? rows : []);
    cache.set(cacheKey, { at: Date.now(), signal });
    return signal;
  } catch {
    const miss: GitlabBranchDeploySignal = {
      status: 'unavailable',
      webUrl: null,
      inFlight: false,
    };
    cache.set(cacheKey, { at: Date.now(), signal: miss });
    return miss;
  }
}

/**
 * @deprecated Prefer getGitlabBranchDeploySignal — kept for callers that only need status/webUrl.
 */
export async function getLatestGitlabPipelineDeployStatus(options: {
  gitlabProject: string;
  branch: string;
}): Promise<{ status: GitlabPipelineDeployStatus; webUrl: string | null }> {
  const signal = await getGitlabBranchDeploySignal(options);
  return { status: signal.status, webUrl: signal.webUrl };
}
