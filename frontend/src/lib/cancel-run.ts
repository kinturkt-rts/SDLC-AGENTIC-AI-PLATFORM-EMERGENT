import { promises as fs } from 'fs';
import path from 'path';
import { getBackendRoot } from './repo-root';
import { getRunArtifactJson, isS3Store, putRunArtifact } from './artifact-store';
import { stopRuntimeSession } from './agentcore-invoke';
import { invalidateRunsCache } from './runs-cache';

export interface CancelRunResult {
  runId: string;
  status: 'cancelled';
  sessionStopped: boolean;
  message: string;
  stopError?: string;
}

interface RunJsonDoc {
  runId?: string;
  feature?: string;
  targetApp?: string;
  status?: string;
  error?: string | null;
  finishedAt?: string | null;
  currentStep?: string | null;
  steps?: Array<{ name: string; status?: string }>;
  orchestratorSessionId?: string | null;
  orchestratorRuntimeArn?: string | null;
  [key: string]: unknown;
}

function localRunJsonPath(runId: string): string {
  return path.join(getBackendRoot(), 'agents', 'pipeline', 'runs', runId, 'run.json');
}

async function readRunJson(runId: string): Promise<RunJsonDoc | null> {
  if (isS3Store()) {
    const doc = (await getRunArtifactJson(runId, 'run.json')) as RunJsonDoc | null;
    if (doc) return doc;
  }
  try {
    let raw = await fs.readFile(localRunJsonPath(runId), 'utf-8');
    if (raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
    return JSON.parse(raw) as RunJsonDoc;
  } catch {
    return null;
  }
}

async function writeRunJson(runId: string, data: RunJsonDoc): Promise<void> {
  const body = `${JSON.stringify(data, null, 2)}\n`;
  const local = localRunJsonPath(runId);
  await fs.mkdir(path.dirname(local), { recursive: true });
  await fs.writeFile(local, body, 'utf-8');
  if (isS3Store()) {
    await putRunArtifact(runId, 'run.json', body, 'application/json');
  }
}

/**
 * Soft-cancel run.json (frees concurrency slot) and hard-stop the orchestrator
 * AgentCore session when we have a runtimeSessionId.
 */
export async function cancelPipelineRun(runId: string): Promise<CancelRunResult> {
  const id = runId.trim();
  if (!id) throw new Error('runId is required');

  const doc = await readRunJson(id);
  if (!doc) throw new Error(`Run not found: ${id}`);

  const status = String(doc.status ?? '').toLowerCase();
  if (status === 'completed' || status === 'failed' || status === 'cancelled') {
    throw new Error(`Run is already ${status} and cannot be cancelled`);
  }

  const sessionId =
    typeof doc.orchestratorSessionId === 'string' ? doc.orchestratorSessionId.trim() : '';
  const runtimeArn =
    typeof doc.orchestratorRuntimeArn === 'string' ? doc.orchestratorRuntimeArn.trim() : null;

  let sessionStopped = false;
  let stopError: string | undefined;
  if (sessionId) {
    const stopped = await stopRuntimeSession('orchestrator-agent', sessionId, runtimeArn);
    sessionStopped = stopped.ok;
    if (!stopped.ok) stopError = stopped.error;
  }

  const now = new Date().toISOString();

  const userError = sessionStopped
    ? 'Cancelled by user'
    : sessionId
      ? 'Cancelled by user. Cloud work may take a moment to stop.'
      : 'Cancelled by user. Cloud work may take a moment to stop.';
  const next: RunJsonDoc = {
    ...doc,
    runId: doc.runId || id,
    status: 'cancelled',
    finishedAt: now,
    currentStep: null,
    error: userError,
  };
  if (Array.isArray(next.steps)) {
    next.steps = next.steps.map((step) =>
      step.status === 'running' ? { ...step, status: 'failed' as const } : step,
    );
  }

  await writeRunJson(id, next);
  invalidateRunsCache();

  const message = sessionStopped
    ? 'This run was cancelled.'
    : 'This run was cancelled. Any remaining cloud work should stop shortly.';

  return {
    runId: id,
    status: 'cancelled',
    sessionStopped,
    message,
    ...(stopError ? { stopError } : {}),
  };
}
