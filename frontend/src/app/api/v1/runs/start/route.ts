import { promises as fs } from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { NextResponse } from 'next/server';
import { getBackendRoot } from '@/src/lib/repo-root';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const SLUG_RE = /^[a-z][a-z0-9-]{1,63}$/;

interface StartBody {
  feature?: unknown;
  inputPath?: unknown;
}

function bad(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

async function resolvePythonExecutable(repoRoot: string): Promise<string> {
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

async function fileExists(p: string): Promise<boolean> {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

export async function POST(request: Request) {
  let body: StartBody;
  try {
    body = (await request.json()) as StartBody;
  } catch {
    return bad('Body must be JSON: { feature, inputPath? }');
  }

  const feature = typeof body.feature === 'string' ? body.feature.trim().toLowerCase() : '';
  if (!feature) return bad('feature is required');
  if (!SLUG_RE.test(feature)) {
    return bad('feature must be lowercase letters, digits, dashes; start with a letter; <=64 chars');
  }

  const repoRoot = getBackendRoot();
  const inputRel = typeof body.inputPath === 'string' && body.inputPath ? body.inputPath : `inputs/${feature}.txt`;
  const absInput = path.resolve(repoRoot, ...inputRel.replace(/\\/g, '/').split('/'));
  if (!absInput.startsWith(path.resolve(repoRoot) + path.sep)) {
    return bad('inputPath escapes the repo root');
  }
  if (!(await fileExists(absInput))) {
    return bad(`input file not found: ${inputRel}. POST /api/v1/inputs first.`, 404);
  }

  const runId = `run-${feature}`;
  const runStatePath = path.join(repoRoot, 'agents', 'pipeline', `${feature}.run.json`);
  await fs.mkdir(path.dirname(runStatePath), { recursive: true });
  await fs.writeFile(
    runStatePath,
    JSON.stringify(
      {
        runId,
        feature,
        status: 'queued',
        triggeredBy: 'frontend',
        startedAt: null,
        finishedAt: null,
        currentStep: null,
        inputPath: inputRel,
        error: null,
        steps: [
          { name: 'product-agent', label: '1/5 Product (PRD)', status: 'queued' },
          { name: 'architect-agent', label: '2/5 Architect (design + diagram)', status: 'queued' },
          { name: 'database-agent', label: '3/5 Database (SQL migrations)', status: 'queued' },
          { name: 'developer-agent', label: '4/5 Developer (FastAPI)', status: 'queued' },
          { name: 'gitlab-agent', label: '5/5 GitLab publish', status: 'queued' },
        ],
      },
      null,
      2,
    ) + '\n',
    'utf-8',
  );

  const python = await resolvePythonExecutable(repoRoot);
  const args = [
    '-m',
    'orchestrator.sdlc_pipeline',
    '--feature',
    feature,
    '--input-file',
    inputRel,
    '--run-id',
    runId,
  ];

  const logsDir = path.join(repoRoot, 'agents', 'pipeline', '.logs');
  await fs.mkdir(logsDir, { recursive: true });
  const logPath = path.join(logsDir, `${feature}.log`);

  try {
    const child = spawn(python, args, {
      cwd: repoRoot,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
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

    return NextResponse.json({
      runId,
      feature,
      pid: child.pid,
      inputPath: inputRel,
      logPath: path.relative(repoRoot, logPath).replace(/\\/g, '/'),
      runStatePath: path.relative(repoRoot, runStatePath).replace(/\\/g, '/'),
      orchestratorCommand: `${python} ${args.join(' ')}`,
      startedAt: new Date().toISOString(),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: `failed to spawn orchestrator: ${message}` }, { status: 500 });
  }
}
