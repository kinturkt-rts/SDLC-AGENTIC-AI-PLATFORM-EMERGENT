import { promises as fs } from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';
import { spawn } from 'child_process';
import { getBackendRoot } from './repo-root';
import { isS3Store, putRunArtifact, runInputRelPath, runInputS3Uri } from './artifact-store';

const SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
/** Human-friendly run ids (e.g. smoke-004) or UUIDs — matches agent pipeline runId usage. */
const RUN_ID_RE = /^(?:[a-z][a-z0-9-]{0,62}[a-z0-9]|[0-9a-f-]{36})$/i;
const MAX_BYTES = 256 * 1024;

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
      // try next
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

/** Stage brief under runs/<runId>/inputs/<targetApp>.txt (always a fresh runId unless provided). */
export async function uploadBrief(
  targetApp: string,
  content: string,
  runId?: string,
): Promise<UploadBriefResult> {
  const slugError = validateTargetApp(targetApp);
  if (slugError) throw new Error(slugError);
  if (!content.trim()) throw new Error('content is empty');

  const slug = targetApp.trim().toLowerCase();
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
  if (isS3Store()) {
    await putRunArtifact(id, inputFile, content, 'text/plain; charset=utf-8');
  } else {
    await putRunArtifact(id, inputFile, content, 'text/plain; charset=utf-8');
  }

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
}): Promise<StartPipelineResult> {
  const slugError = validateTargetApp(options.targetApp);
  if (slugError) throw new Error(slugError);
  const runErr = validateRunId(options.runId);
  if (runErr) throw new Error(runErr);

  const feature = options.targetApp.trim().toLowerCase();
  const runId = options.runId.trim();
  const inputRel = options.inputFile.trim() || runInputRelPath(feature);
  const repoRoot = getBackendRoot();

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
        triggeredBy: 'frontend',
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

  const python = await resolvePythonExecutable(repoRoot);
  const orchestratorScript = path.join(repoRoot, 'agents', 'orchestrator-agent', 'orchestrator_agent.py');
  const transport = (process.env.SDLC_PIPELINE_TRANSPORT?.trim().toLowerCase() || 'auto') as
    | 'auto'
    | 'local'
    | 'a2a';
  const args = [
    orchestratorScript,
    '--run-pipeline',
    '--target-app',
    feature,
    '--run-id',
    runId,
    '--input-file',
    inputRel,
    '--transport',
    transport,
  ];

  const logsDir = path.join(repoRoot, 'agents', 'pipeline', '.logs');
  await fs.mkdir(logsDir, { recursive: true });
  const logPath = path.join(logsDir, `${runId}.log`);

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

/** One submission: new runId, upload brief, start orchestrator. */
export async function submitBrief(targetApp: string, content: string) {
  const upload = await uploadBrief(targetApp, content);
  const started = await startPipeline({
    targetApp: upload.targetApp,
    runId: upload.runId,
    inputFile: upload.inputFile,
  });
  return { ...upload, ...started };
}
