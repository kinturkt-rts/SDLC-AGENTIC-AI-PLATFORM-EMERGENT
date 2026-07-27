import { promises as fs } from 'fs';
import path from 'path';
import { getBackendRoot } from './repo-root';
import { getRunArtifactJson, getS3RunContext, isS3Store } from './artifact-store';
import type { DeveloperHandoffInfo, DevopsHandoffInfo, GitlabHandoffInfo, RunHandoffs } from '@/src/types';

type HandoffRecord = Record<string, unknown>;

async function readLocalPipelineJson(rel: string): Promise<HandoffRecord | null> {
  const filePath = path.join(getBackendRoot(), ...rel.replace(/\\/g, '/').split('/'));
  try {
    let raw = await fs.readFile(filePath, 'utf-8');
    if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
    const parsed = JSON.parse(raw) as unknown;
    return parsed && typeof parsed === 'object' ? (parsed as HandoffRecord) : null;
  } catch {
    return null;
  }
}

/**
 * Normalize GitLab branch browse links for the UI.
 * Older handoffs used ``/-/tree/sdlc%2Fapp``; GitLab prefers
 * ``/-/tree/sdlc/app?ref_type=heads``.
 */
export function normalizeGitlabBranchUrl(url: string | null | undefined): string | null {
  const raw = typeof url === 'string' ? url.trim() : '';
  if (!raw) return null;

  try {
    const parsed = new URL(raw);
    const marker = '/-/tree/';
    const idx = parsed.pathname.indexOf(marker);
    if (idx >= 0) {
      const prefix = parsed.pathname.slice(0, idx + marker.length);
      const encodedBranch = parsed.pathname.slice(idx + marker.length);
      const branchPath = decodeURIComponent(encodedBranch).replace(/^\/+/, '');
      parsed.pathname = `${prefix}${branchPath}`;
      if (!parsed.searchParams.has('ref_type')) {
        parsed.searchParams.set('ref_type', 'heads');
      }
      return parsed.toString();
    }
  } catch {
    // Fall through for non-absolute / odd values.
  }

  return raw.replace(/%2F/gi, '/');
}

function parseGitlabHandoff(
  data: HandoffRecord,
  source: 's3' | 'local',
  artifactPath: string,
): GitlabHandoffInfo {
  const paths = Array.isArray(data.pathsPublished) ? data.pathsPublished : [];
  const iid = data.mergeRequestIid;
  return {
    status: String(data.status ?? 'unknown'),
    branch: typeof data.branch === 'string' ? data.branch : null,
    branchUrl: normalizeGitlabBranchUrl(
      typeof data.branchUrl === 'string' ? data.branchUrl : null,
    ),
    mergeRequestUrl: typeof data.mergeRequestUrl === 'string' ? data.mergeRequestUrl : null,
    mergeRequestIid: typeof iid === 'number' ? iid : null,
    gitlabProject: typeof data.gitlabProject === 'string' ? data.gitlabProject : null,
    repoUrl: typeof data.repoUrl === 'string' ? data.repoUrl : null,
    pathsPublishedCount: paths.length,
    error: typeof data.error === 'string' ? data.error : null,
    source,
    path: artifactPath,
  };
}

function parseValidationStatus(data: HandoffRecord): 'passed' | 'failed' | null {
  if (data.validationPassed === true) return 'passed';
  if (data.validationPassed === false) return 'failed';
  const raw = data.validationStatus;
  if (typeof raw === 'string') {
    const normalized = raw.trim().toLowerCase();
    if (normalized === 'passed' || normalized === 'success') return 'passed';
    if (normalized === 'failed' || normalized === 'error') return 'failed';
  }
  return null;
}

function parseDeveloperHandoff(
  data: HandoffRecord,
  source: 's3' | 'local',
  artifactPath: string,
): DeveloperHandoffInfo {
  const files = Array.isArray(data.writtenFiles) ? data.writtenFiles : [];
  return {
    targetApp: String(data.targetApp ?? ''),
    status: String(data.status ?? 'unknown'),
    writtenFilesCount: files.length,
    validationStatus: parseValidationStatus(data),
    error: typeof data.error === 'string' ? data.error : null,
    source,
    path: artifactPath,
  };
}

function parseDevopsHandoff(
  data: HandoffRecord,
  source: 's3' | 'local',
  artifactPath: string,
): DevopsHandoffInfo {
  const appUrl = typeof data.appUrl === 'string' ? data.appUrl.trim() : '';
  const healthy = typeof data.healthy === 'boolean' ? data.healthy : null;
  let status = typeof data.status === 'string' ? data.status : '';
  if (!status) {
    if (appUrl && healthy !== false) status = 'healthy';
    else if (appUrl) status = 'deployed';
    else if (healthy === false && data.deployedAt) status = 'failed';
    else if (data.tfRootPresent === true) status = 'tf_ready';
    else status = 'unknown';
  }
  return {
    status,
    targetApp: String(data.targetApp ?? ''),
    appUrl: appUrl || null,
    environment: typeof data.environment === 'string' ? data.environment : null,
    region: typeof data.region === 'string' ? data.region : null,
    healthy,
    ecsService: typeof data.ecsService === 'string' ? data.ecsService : null,
    deployedAt: typeof data.deployedAt === 'string' ? data.deployedAt : null,
    error: typeof data.error === 'string' ? data.error : null,
    source,
    path: artifactPath,
  };
}

async function loadFirstGitlabHandoff(
  runId: string,
  slug: string,
): Promise<GitlabHandoffInfo | null> {
  const candidates: Array<{ source: 's3' | 'local'; path: string; loader: () => Promise<HandoffRecord | null> }> = [
    {
      source: 's3',
      path: `runs/${runId}/${slug}/handoffs/gitlab-handoff.json`,
      loader: () => getRunArtifactJson(runId, `${slug}/handoffs/gitlab-handoff.json`),
    },
    {
      source: 's3',
      path: `runs/${runId}/handoffs/gitlab.json`,
      loader: () => getRunArtifactJson(runId, 'handoffs/gitlab.json'),
    },
  ];
  // Legacy slug-keyed files (agents/pipeline/<slug>.gitlab-handoff.json) are only valid
  // for local-CLI runs. In cloud/S3 mode they are stale repo leftovers from older runs
  // of the same app slug: reading them here made brand-new runs show "published" with
  // dead branch URLs and let the publish gate skip gitlab-agent entirely.
  if (!isS3Store()) {
    candidates.push(
      {
        source: 'local',
        path: `agents/pipeline/${slug}.gitlab-handoff.json`,
        loader: () => readLocalPipelineJson(`agents/pipeline/${slug}.gitlab-handoff.json`),
      },
      {
        source: 'local',
        path: `agents/pipeline/runs/${runId}/${slug}/handoffs/gitlab-handoff.json`,
        loader: () => getRunArtifactJson(runId, `${slug}/handoffs/gitlab-handoff.json`),
      },
    );
  }

  for (const candidate of candidates) {
    const data = await candidate.loader();
    if (data) return parseGitlabHandoff(data, candidate.source, candidate.path);
  }
  return null;
}

async function loadFirstDeveloperHandoff(
  runId: string,
  slug: string,
): Promise<DeveloperHandoffInfo | null> {
  const candidates: Array<{ source: 's3' | 'local'; path: string; loader: () => Promise<HandoffRecord | null> }> = [
    {
      source: 's3',
      path: `runs/${runId}/${slug}/handoffs/developer-handoff.json`,
      loader: () => getRunArtifactJson(runId, `${slug}/handoffs/developer-handoff.json`),
    },
  ];
  // Same stale-slug-file hazard as gitlab handoffs: only trust these in local mode.
  if (!isS3Store()) {
    candidates.push(
      {
        source: 'local',
        path: `agents/pipeline/${slug}.developer-handoff.json`,
        loader: () => readLocalPipelineJson(`agents/pipeline/${slug}.developer-handoff.json`),
      },
      {
        source: 'local',
        path: `agents/pipeline/runs/${runId}/${slug}/handoffs/developer-handoff.json`,
        loader: () => getRunArtifactJson(runId, `${slug}/handoffs/developer-handoff.json`),
      },
    );
  }

  for (const candidate of candidates) {
    const data = await candidate.loader();
    if (data) return parseDeveloperHandoff(data, candidate.source, candidate.path);
  }
  return null;
}

async function loadFirstDevopsHandoff(
  runId: string,
  slug: string,
): Promise<DevopsHandoffInfo | null> {
  const candidates: Array<{ source: 's3' | 'local'; path: string; loader: () => Promise<HandoffRecord | null> }> = [
    {
      source: 's3',
      path: `runs/${runId}/${slug}/handoffs/devops-handoff.json`,
      loader: () => getRunArtifactJson(runId, `${slug}/handoffs/devops-handoff.json`),
    },
    {
      source: 's3',
      path: `runs/${runId}/handoffs/devops.json`,
      loader: () => getRunArtifactJson(runId, 'handoffs/devops.json'),
    },
  ];
  if (!isS3Store()) {
    candidates.push(
      {
        source: 'local',
        path: `agents/pipeline/${slug}.devops-handoff.json`,
        loader: () => readLocalPipelineJson(`agents/pipeline/${slug}.devops-handoff.json`),
      },
      {
        source: 'local',
        path: `agents/pipeline/runs/${runId}/${slug}/handoffs/devops-handoff.json`,
        loader: () => getRunArtifactJson(runId, `${slug}/handoffs/devops-handoff.json`),
      },
    );
  }

  for (const candidate of candidates) {
    const data = await candidate.loader();
    if (data) return parseDevopsHandoff(data, candidate.source, candidate.path);
  }
  return null;
}

/** GitLab branch/repo link for project overview when a publish handoff exists. */
export async function resolveGitlabRepositoryLink(
  runId: string,
  slug: string,
): Promise<{ label: string; href: string } | null> {
  const gitlab = await loadFirstGitlabHandoff(runId, slug.trim().toLowerCase());
  if (!gitlab) return null;
  const href = gitlab.branchUrl ?? gitlab.repoUrl;
  if (!href) return null;
  return {
    label: gitlab.branch ?? `sdlc/${slug.trim().toLowerCase()}`,
    href,
  };
}

/** Readable repository label + href for project cards (GitLab branch or latest run). */
export async function resolveProjectRepositoryLink(
  slug: string,
  runId?: string | null,
): Promise<{ label: string; href: string | null; external: boolean }> {
  const normalized = slug.trim().toLowerCase();
  const localFallback = {
    label: `target-apps/${normalized}`,
    href: null as string | null,
    external: false,
  };

  if (runId) {
    const gitlab = await resolveGitlabRepositoryLink(runId, normalized);
    if (gitlab) {
      return { label: gitlab.label, href: gitlab.href, external: true };
    }
    return {
      label: `Run ${runId.slice(0, 8)}`,
      href: `/runs/${runId}`,
      external: false,
    };
  }

  const localGitlab = isS3Store()
    ? null
    : await readLocalPipelineJson(`agents/pipeline/${normalized}.gitlab-handoff.json`);
  if (localGitlab) {
    const href =
      (typeof localGitlab.branchUrl === 'string' && localGitlab.branchUrl) ||
      (typeof localGitlab.repoUrl === 'string' && localGitlab.repoUrl) ||
      null;
    if (href) {
      const branch =
        typeof localGitlab.branch === 'string' ? localGitlab.branch : `sdlc/${normalized}`;
      return { label: branch, href, external: true };
    }
  }

  return localFallback;
}

/** True when this run has a GitLab publish handoff in S3 or local run storage. */
export async function gitlabHandoffExistsForRun(runId: string, slug: string): Promise<boolean> {
  const normalized = slug.trim().toLowerCase();
  const candidates = [
    `handoffs/gitlab.json`,
    `${normalized}/handoffs/gitlab-handoff.json`,
    `agents/pipeline/${normalized}.gitlab-handoff.json`,
  ];
  for (const rel of candidates) {
    const doc = await getRunArtifactJson(runId, rel);
    if (doc) return true;
  }
  if (!isS3Store()) {
    const local = await readLocalPipelineJson(`agents/pipeline/${normalized}.gitlab-handoff.json`);
    if (local) return true;
  }
  return false;
}

/** True only when a GitLab publish handoff exists AND it actually succeeded. */
export async function gitlabPublishSucceededForRun(runId: string, slug: string): Promise<boolean> {
  const gitlab = await loadFirstGitlabHandoff(runId, slug.trim().toLowerCase());
  if (!gitlab) return false;
  const status = (gitlab.status ?? '').toLowerCase();
  if (status === 'failed' || status === 'error') return false;
  return Boolean(gitlab.branchUrl || gitlab.repoUrl || gitlab.mergeRequestUrl || status === 'published' || status === 'already-published');
}

/** True when developer-agent wrote its completion handoff for this run. */
export async function developerHandoffExistsForRun(runId: string, slug: string): Promise<boolean> {
  return (await loadFirstDeveloperHandoff(runId, slug.trim().toLowerCase())) !== null;
}

/** True only when developer-agent reached a successful terminal handoff. */
export async function developerHandoffSucceededForRun(
  runId: string,
  slug: string,
): Promise<boolean> {
  const developer = await loadFirstDeveloperHandoff(runId, slug.trim().toLowerCase());
  if (!developer) return false;
  const status = developer.status.trim().toLowerCase();
  if (status === 'failed' || status === 'error' || developer.validationStatus === 'failed') {
    return false;
  }
  return status === 'completed' || developer.validationStatus === 'passed';
}

/** True only when developer-agent explicitly failed (not in_progress). */
export async function developerHandoffFailedForRun(
  runId: string,
  slug: string,
): Promise<boolean> {
  const developer = await loadFirstDeveloperHandoff(runId, slug.trim().toLowerCase());
  if (!developer) return false;
  const status = developer.status.trim().toLowerCase();
  return status === 'failed' || status === 'error' || developer.validationStatus === 'failed';
}

/**
 * Prefer concrete handoff / run errors over generic "check handoffs" copy.
 * Returns null when there is nothing more specific than the reconciler's default.
 */
export async function resolveRunFailureDetail(
  runId: string,
  slug: string,
): Promise<string | null> {
  const normalized = slug.trim().toLowerCase();
  const [developer, gitlab] = await Promise.all([
    loadFirstDeveloperHandoff(runId, normalized),
    loadFirstGitlabHandoff(runId, normalized),
  ]);

  if (developer) {
    const status = developer.status.trim().toLowerCase();
    if (developer.error?.trim()) {
      return `Developer-agent failed: ${developer.error.trim()}`;
    }
    if (status === 'failed' || status === 'error' || developer.validationStatus === 'failed') {
      return 'Developer-agent reported failure (see developer handoff).';
    }
    if (status === 'in_progress' || status === 'running') {
      return (
        'Developer-agent did not finish (handoff still in_progress - runtime likely timed out ' +
        'before writing a terminal status).'
      );
    }
  }

  if (gitlab) {
    const status = (gitlab.status ?? '').toLowerCase();
    if (gitlab.error?.trim()) {
      return `GitLab publish failed: ${gitlab.error.trim()}`;
    }
    if (status === 'failed' || status === 'error') {
      return 'GitLab publish reported failure (see GitLab handoff).';
    }
  }

  return null;
}

/** Poll until developer-handoff.json reports success. */
export async function waitForDeveloperHandoffForRun(
  runId: string,
  slug: string,
  options?: { timeoutSec?: number; pollIntervalMs?: number },
): Promise<boolean> {
  const timeoutSec = options?.timeoutSec ?? 900;
  const pollIntervalMs = options?.pollIntervalMs ?? 5000;
  const deadline = Date.now() + timeoutSec * 1000;
  const normalized = slug.trim().toLowerCase();

  while (Date.now() < deadline) {
    if (await developerHandoffSucceededForRun(runId, normalized)) return true;
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
  }
  return false;
}

/** True when devops-agent produced a usable live app URL for this run. */
export async function devopsDeploySucceededForRun(runId: string, slug: string): Promise<boolean> {
  const devops = await loadFirstDevopsHandoff(runId, slug.trim().toLowerCase());
  if (!devops) return false;
  const status = devops.status.trim().toLowerCase();
  if (status === 'failed' || status === 'error') return false;
  return Boolean(devops.appUrl);
}

/** True when a completed deploy attempt explicitly failed its health check. */
export async function devopsDeployFailedForRun(runId: string, slug: string): Promise<boolean> {
  const devops = await loadFirstDevopsHandoff(runId, slug.trim().toLowerCase());
  if (!devops) return false;
  const status = devops.status.trim().toLowerCase();
  return (
    devops.healthy === false ||
    status === 'failed' ||
    status === 'error' ||
    status === 'destroyed'
  );
}

/** True when a devops handoff exists (even if still deploying / no URL yet). */
export async function devopsHandoffExistsForRun(runId: string, slug: string): Promise<boolean> {
  return (await loadFirstDevopsHandoff(runId, slug.trim().toLowerCase())) !== null;
}

/** Load gitlab + developer + devops handoffs for a run (S3 run store and local slug files). */
export async function getRunHandoffs(runId: string, projectSlug: string): Promise<RunHandoffs> {
  const slug = projectSlug.trim().toLowerCase();
  const [gitlab, developer, devops, ctx] = await Promise.all([
    loadFirstGitlabHandoff(runId, slug),
    loadFirstDeveloperHandoff(runId, slug),
    loadFirstDevopsHandoff(runId, slug),
    isS3Store() ? getS3RunContext(runId) : getRunArtifactJson(runId, `${slug}/context.json`),
  ]);

  const contextMergeRequestUrl =
    typeof ctx?.mergeRequestUrl === 'string' ? ctx.mergeRequestUrl : null;
  const contextFeatureBranch =
    typeof ctx?.featureBranch === 'string' ? ctx.featureBranch : null;

  return {
    runId,
    projectSlug: slug,
    gitlab,
    developer,
    devops,
    contextMergeRequestUrl,
    contextFeatureBranch,
  };
}
