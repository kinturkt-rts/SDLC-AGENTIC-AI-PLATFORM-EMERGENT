import { promises as fs } from 'fs';
import path from 'path';
import { getBackendRoot } from './repo-root';
import { getRunArtifactJson, getS3RunContext, isS3Store } from './artifact-store';
import type { DeveloperHandoffInfo, GitlabHandoffInfo, RunHandoffs } from '@/src/types';

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
    branchUrl: typeof data.branchUrl === 'string' ? data.branchUrl : null,
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
    writtenFilesCount: files.length,
    validationStatus: parseValidationStatus(data),
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
  ];

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
  ];

  for (const candidate of candidates) {
    const data = await candidate.loader();
    if (data) return parseDeveloperHandoff(data, candidate.source, candidate.path);
  }
  return null;
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

/** Load gitlab + developer handoffs for a run (S3 run store and local slug files). */
export async function getRunHandoffs(runId: string, projectSlug: string): Promise<RunHandoffs> {
  const slug = projectSlug.trim().toLowerCase();
  const [gitlab, developer, ctx] = await Promise.all([
    loadFirstGitlabHandoff(runId, slug),
    loadFirstDeveloperHandoff(runId, slug),
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
    contextMergeRequestUrl,
    contextFeatureBranch,
  };
}
