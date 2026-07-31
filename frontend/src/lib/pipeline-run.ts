import { promises as fs } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import { spawn } from 'child_process';
import { getBackendRoot } from './repo-root';
import { isS3Store, putRunArtifact, runInputRelPath, runInputS3Uri } from './artifact-store';
import { withTimeout } from './async-utils';
import { invalidateCacheKeys } from './request-cache';
import { finalizeRunJson, runOrchestratorCloud } from './orchestrator-cloud-run';
import { listRunGuardCandidates, listRuns } from './repo-reader';
import { RUN_LIVE_IDLE_MS } from './run-reconcile';
import { validateProductBrief } from './brief-quality';

const RUNS_CACHE_KEYS = [
  'listRuns',
  's3RunArtifactIndex',
  'getDashboardSummary',
  'listProjects',
  'listArtifacts',
  'listRecentActivity:12',
];

const SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const RUN_ID_RE = /^(?:[a-z][a-z0-9-]{0,62}[a-z0-9]|[0-9a-f-]{36})$/i;
const MAX_BYTES = 256 * 1024;
const S3_UPLOAD_TIMEOUT_MS = 45_000;
const MAX_CONCURRENT_RUNS = Math.max(1, parseInt(process.env.SDLC_MAX_CONCURRENT_RUNS ?? '3', 10) || 3);
const RUN_STALL_MS = RUN_LIVE_IDLE_MS;

export function isDeployFollowOn(run: {
  status?: string;
  currentPhase?: string | null;
  currentAgent?: string | null;
  deployStatus?: string | null;
}): boolean {
  if (run.deployStatus === 'failed' || run.deployStatus === 'stale') return false;
  if (run.deployStatus === 'pending' || run.deployStatus === 'running') return true;
  if (run.status === 'awaiting_deploy') return true;
  return (
    run.status === 'running' &&
    (run.currentPhase === 'deploy' || run.currentAgent === 'devops-agent')
  );
}

/** Active pipeline runs that still occupy a concurrency slot (agent chain only). */
export async function getActiveRuns() {
  try {
    const runs = await listRuns();
    return runs.filter((r) => {
      if (r.status === 'paused') return true;
      if (r.status !== 'running') return false;
      return !isDeployFollowOn(r);
    });
  } catch {
    return [];
  }
}

export async function findRunningTargetApp(targetApp: string) {
  const slug = targetApp.trim().toLowerCase();
  try {
    const runs = await listRuns();
    return (
      runs.find(
        (r) =>
          r.projectId === slug &&
          (r.status === 'running' ||
            r.status === 'paused' ||
            r.status === 'awaiting_deploy' ||
            r.deployStatus === 'pending' ||
            r.deployStatus === 'running'),
      ) ?? null
    );
  } catch {
    return null;
  }
}

export function maxConcurrentRuns(): number {
  return MAX_CONCURRENT_RUNS;
}

export function validateRunId(runId: string): string | null {
  const id = runId.trim();
  if (!id) return 'runId is required';
  if (UUID_RE.test(id) || RUN_ID_RE.test(id)) return null;
  return 'runId must be a UUID or slug like smoke-004';
}

export function validateTargetApp(targetApp: string): string | null {
  const slug = targetApp.trim().toLowerCase();
  if (!slug) return 'targetApp is required';
  if (!SLUG_RE.test(slug)) {
    return 'targetApp must be lowercase letters, digits, dashes; start with a letter; <=64 chars';
  }
  return null;
}

export async function resolvePythonExecutable(repoRoot: string): Promise<string> {
  const override = process.env.ORCHESTRATOR_PYTHON?.trim();
  if (override) return override;

  const candidates = [
    path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),
    path.join(repoRoot, '.venv', 'bin', 'python'),
    path.join(repoRoot, 'venv', 'Scripts', 'python.exe'),
    path.join(repoRoot, 'venv', 'bin', 'python'),
  ];
  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
    }
  }
  return 'python';
}

export interface UploadBriefResult {
  runId: string;
  targetApp: string;
  inputFile: string;
  bytes: number;
  artifactStore: 's3' | 'local';
  inputS3Uri?: string;
  runPrefix: string;
}

export interface ExistingProjectInfo {
  projectId: string;
  runCount: number;
  firstSeenAt: string;
  lastRunAt: string;
  lastRunStatus: string;
}

export class ExistingProjectConflictError extends Error {
  constructor(public readonly project: ExistingProjectInfo) {
    super(
      `"${project.projectId}" already exists (${project.runCount} previous run` +
        `${project.runCount === 1 ? '' : 's'}, last ${project.lastRunStatus}). Confirm you want to ` +
        'continue this existing app, or choose a different name.',
    );
    this.name = 'ExistingProjectConflictError';
  }
}

/** Pure: given a full run list, summarize this slug's prior runs (or null if never used). */
export function summarizeExistingProject(
  runs: { projectId: string; startedAt: string; status: string }[],
  slug: string,
): ExistingProjectInfo | null {
  const matches = runs.filter((r) => r.projectId === slug);
  if (matches.length === 0) return null;

  const sorted = [...matches].sort((a, b) => a.startedAt.localeCompare(b.startedAt));
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  return {
    projectId: slug,
    runCount: matches.length,
    firstSeenAt: first.startedAt,
    lastRunAt: last.startedAt,
    lastRunStatus: last.status,
  };
}

/** Null when this slug has never been used; otherwise a summary of its prior runs. */
export async function findExistingProject(slug: string): Promise<ExistingProjectInfo | null> {
  const runs = await listRuns();
  return summarizeExistingProject(runs, slug);
}

export async function uploadBrief(
  targetApp: string,
  content: string,
  runId?: string,
  options?: { confirmExistingProject?: boolean },
): Promise<UploadBriefResult> {
  const slugError = validateTargetApp(targetApp);
  if (slugError) throw new Error(slugError);
  const briefError = validateProductBrief(content);
  if (briefError) throw new Error(briefError);

  const slug = targetApp.trim().toLowerCase();

  if (!options?.confirmExistingProject) {
    const existing = await findExistingProject(slug);
    if (existing) throw new ExistingProjectConflictError(existing);
  }
  const byteLen = Buffer.byteLength(content, 'utf-8');
  if (byteLen > MAX_BYTES) {
    throw new Error(`content too large (${byteLen} bytes; limit ${MAX_BYTES})`);
  }

  let id = runId?.trim() ?? '';
  if (id) {
    const runErr = validateRunId(id);
    if (runErr) throw new Error(runErr);
  } else {
    id = randomUUID();
  }

  const inputFile = runInputRelPath(slug);
  const putPromise = putRunArtifact(id, inputFile, content, 'text/plain; charset=utf-8');
  if (isS3Store()) {
    await withTimeout(putPromise, S3_UPLOAD_TIMEOUT_MS, 'S3 upload');
  } else {
    await putPromise;
  }

  invalidateCacheKeys(...RUNS_CACHE_KEYS);

  return {
    runId: id,
    targetApp: slug,
    inputFile,
    bytes: byteLen,
    artifactStore: isS3Store() ? 's3' : 'local',
    ...(isS3Store() ? { inputS3Uri: runInputS3Uri(id, slug) } : {}),
    runPrefix: `runs/${id}/`,
  };
}

export interface StartPipelineResult {
  runId: string;
  targetApp: string;
  inputFile: string;
  pid?: number;
  logPath: string;
  runStatePath: string;
  orchestratorCommand: string;
  startedAt: string;
}

/** Invoke orchestrator with targetApp, runId, inputFile (brief must already be staged). */
export async function startPipeline(options: {
  targetApp: string;
  runId: string;
  inputFile: string;
  withJira?: boolean;
  jiraProject?: string;
  triggeredBy?: string;
}): Promise<StartPipelineResult> {
  const slugError = validateTargetApp(options.targetApp);
  if (slugError) throw new Error(slugError);
  const runErr = validateRunId(options.runId);
  if (runErr) throw new Error(runErr);

  const feature = options.targetApp.trim().toLowerCase();
  const runId = options.runId.trim();
  const inputRel = options.inputFile.trim() || runInputRelPath(feature);
  const repoRoot = getBackendRoot();

  const candidates = (await listRunGuardCandidates()).filter((c) => c.runId !== runId);
  const stalled = (c: { lastActivityMs: number }) =>
    c.lastActivityMs > 0 && Date.now() - c.lastActivityMs > RUN_STALL_MS;

  const duplicate = candidates.find((c) => c.projectId === feature && !stalled(c));
  if (duplicate) {
    throw new Error(
      `"${feature}" already has an active pipeline run (${duplicate.runId.slice(0, 8)}…). Wait for it to finish or cancel it.`,
    );
  }

  const others = candidates.filter(
    (c) =>
      !stalled(c) &&
      c.rawStatus !== 'awaiting_deploy' &&
      !isDeployFollowOn({ status: 'running', currentAgent: c.currentStep }),
  );
  if (others.length >= MAX_CONCURRENT_RUNS) {
    throw new Error(
      `Maximum concurrent runs reached (${others.length}/${MAX_CONCURRENT_RUNS}). Wait for a run to finish or cancel one.`,
    );
  }

  if (!isS3Store()) {
    const runLocalInput = path.join(
      repoRoot,
      'agents',
      'pipeline',
      'runs',
      runId,
      ...inputRel.replace(/\\/g, '/').split('/'),
    );
    try {
      await fs.access(runLocalInput);
    } catch {
      throw new Error(`input file not found: runs/${runId}/${inputRel}`);
    }
  }

  const runStatePath = path.join(repoRoot, 'agents', 'pipeline', 'runs', runId, 'run.json');
  await fs.mkdir(path.dirname(runStatePath), { recursive: true });
  await fs.writeFile(
    runStatePath,
    JSON.stringify(
      {
        runId,
        feature,
        targetApp: feature,
        status: 'running',
        triggeredBy: options.triggeredBy?.trim() || 'frontend',
        startedAt: new Date().toISOString(),
        finishedAt: null,
        currentStep: 'product-agent',
        inputPath: inputRel,
        inputFile: inputRel,
        error: null,
        steps: [
          { name: 'product-agent', label: '1/6 Product (PRD)', status: 'running' },
          { name: 'architect-agent', label: '2/6 Architect (design + diagram)', status: 'queued' },
          { name: 'database-agent', label: '3/6 Database (SQL migrations)', status: 'queued' },
          { name: 'developer-agent', label: '4/6 Developer (FastAPI)', status: 'queued' },
          { name: 'gitlab-agent', label: '5/6 GitLab publish', status: 'queued' },
          { name: 'qa-agent', label: '6/6 QA (optional)', status: 'skipped' },
        ],
      },
      null,
      2,
    ) + '\n',
    'utf-8',
  );

  const skipDeveloper =
    (process.env.SDLC_PIPELINE_SKIP_DEVELOPER ?? 'false').trim().toLowerCase() !== 'false';
  const skipGitlab =
    (process.env.SDLC_PIPELINE_SKIP_GITLAB ?? 'false').trim().toLowerCase() === 'true';
  const skipVerify =
    (process.env.SDLC_PIPELINE_SKIP_VERIFY ?? 'true').trim().toLowerCase() !== 'false';
  const useLocalPythonInvoke =
    (process.env.SDLC_PIPELINE_INVOKE_LOCAL ?? 'false').trim().toLowerCase() === 'true';

  const logsDir = path.join(repoRoot, 'agents', 'pipeline', '.logs');
  await fs.mkdir(logsDir, { recursive: true });
  const logPath = path.join(logsDir, `${runId}.log`);
  const timeoutSec = parseInt(process.env.SDLC_PIPELINE_TIMEOUT_SEC ?? '3600', 10);

  const taskOptions = {
    targetApp: feature,
    runId,
    inputFile: inputRel,
    skipDb: false,
    skipPostgres: false,
    skipDeveloper,
    skipGitlab,
    skipVerify,
    withJira: options.withJira ?? false,
    jiraProject: options.withJira ? (options.jiraProject ?? '').trim() : '',
  };

  if (isS3Store() && !useLocalPythonInvoke) {
    void runOrchestratorCloud({
      ...taskOptions,
      logPath,
      timeoutSec,
    }).catch(async (err) => {
      const message = err instanceof Error ? err.message : String(err);
      await fs.appendFile(logPath, `\n[cloud-invoke] FAILED: ${message}\n`, 'utf-8');

      await finalizeRunJson(runId, {
        status: 'failed',
        error: `Cloud orchestrator invoke failed: ${message.slice(0, 300)}`,
      }).catch(() => {});
    });

    invalidateCacheKeys(...RUNS_CACHE_KEYS);

    return {
      runId,
      targetApp: feature,
      inputFile: inputRel,
      logPath: path.relative(repoRoot, logPath).replace(/\\/g, '/'),
      runStatePath: path.relative(repoRoot, runStatePath).replace(/\\/g, '/'),
      orchestratorCommand: `AgentCore SDK invoke orchestrator-agent (timeout=${timeoutSec}s)`,
      startedAt: new Date().toISOString(),
    };
  }


  const smokeScript = path.join(repoRoot, 'scripts', 'invoke-orchestrator-smoke.py');
  const python = await resolvePythonExecutable(repoRoot);
  const args = [
    smokeScript,
    '--app', feature,
    '--run-id', runId,
    '--input-file', inputRel,
    '--no-skip-db',
    '--no-skip-postgres',
    '--no-apply-rds-local',
    '--timeout', String(timeoutSec),
    ...(skipDeveloper ? ['--skip-developer'] : ['--no-skip-developer']),
    ...(skipGitlab ? ['--skip-gitlab'] : ['--no-skip-gitlab']),
    ...(skipVerify ? ['--skip-verify'] : ['--no-skip-verify']),
  ];

  const child = spawn(python, args, {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
      PIPELINE_RUN_ID: runId,
      ARTIFACT_STORE: process.env.ARTIFACT_STORE ?? 's3',
    },
    detached: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const logStream = await fs.open(logPath, 'a');
  child.stdout?.on('data', (chunk) => {
    void logStream.write(chunk);
  });
  child.stderr?.on('data', (chunk) => {
    void logStream.write(chunk);
  });
  child.on('exit', () => {
    void logStream.close();
  });
  child.unref();

  invalidateCacheKeys(...RUNS_CACHE_KEYS);

  return {
    runId,
    targetApp: feature,
    inputFile: inputRel,
    pid: child.pid,
    logPath: path.relative(repoRoot, logPath).replace(/\\/g, '/'),
    runStatePath: path.relative(repoRoot, runStatePath).replace(/\\/g, '/'),
    orchestratorCommand: `${python} ${args.join(' ')}`,
    startedAt: new Date().toISOString(),
  };
}


export async function submitBrief(
  targetApp: string,
  content: string,
  options?: { confirmExistingProject?: boolean; triggeredBy?: string },
) {
  const upload = await uploadBrief(targetApp, content, undefined, options);
  const started = await startPipeline({
    targetApp: upload.targetApp,
    runId: upload.runId,
    inputFile: upload.inputFile,
    triggeredBy: options?.triggeredBy,
  });
  return { ...upload, ...started };
}