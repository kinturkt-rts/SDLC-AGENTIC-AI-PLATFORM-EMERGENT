import { appendFile, readFile, writeFile, mkdir } from 'fs/promises';
import path from 'path';
import { getBackendRoot } from './repo-root';
import { invalidateRunsCache } from './runs-cache';
import {
  developerHandoffSucceededForRun,
  gitlabPublishSucceededForRun,
  waitForDeveloperHandoffForRun,
} from './pipeline-handoffs';
import { invokeAgentRuntimeA2a } from './agentcore-invoke';
import { getRunArtifactJson, s3RunHasAppCode } from './artifact-store';

const DEV_TASK_DB = [
  'Implement API surface from designDocPath as FastAPI routes.',
  'Read db/HANDOFF.md and every db/sql/*.sql before models. Include Postgres parity',
  '(psycopg + postgresql+psycopg://, dialect-guarded database.py, ENUM/UUID variants),',
  'Pydantic response schemas, baseline pytest, and README setup + uvicorn instructions.',
  'If deliveryProfile.requiresStreamlit is true, add ui/streamlit_app.py per Pattern C.',
  'Ensure the developer handoff (status=completed) is written before finishing.',
].join(' ');

const DEV_TASK_NO_DB =
  'Implement API surface and rules from designDocPath as FastAPI routes, Pydantic schemas, ' +
  'and baseline pytest. README with uvicorn + /docs. Ensure the developer handoff ' +
  '(status=completed) is written before finishing.';

const DEFAULT_DEVELOPER_FALLBACK_MODEL = 'us.anthropic.claude-sonnet-4-6';

export interface PipelineTaskOptions {
  targetApp: string;
  runId: string;
  inputFile: string;
  skipProduct?: boolean;
  skipArchitect?: boolean;
  skipDb?: boolean;
  skipPostgres?: boolean;
  skipDeveloper?: boolean;
  skipGitlab?: boolean;
  skipVerify?: boolean;
  withJira?: boolean;
  jiraProject?: string;
}

export function buildOrchestratorTask(options: PipelineTaskOptions): string {
  const payload = {
    target_app: options.targetApp,
    run_id: options.runId,
    input_file: options.inputFile,
    transport: 'a2a',
    skip_product: options.skipProduct ?? false,
    skip_architect: options.skipArchitect ?? false,
    skip_db: options.skipDb ?? false,
    skip_postgres: options.skipPostgres ?? false,
    skip_developer: options.skipDeveloper ?? false,
    skip_gitlab: options.skipGitlab ?? false,
    skip_verify: options.skipVerify ?? true,
    with_jira: options.withJira ?? false,
    jira_project: options.withJira ? (options.jiraProject ?? '').trim() : '',
  };
  return `Run run_sdlc_pipeline with:\n\n${JSON.stringify(payload, null, 2)}`;
}

async function appendLog(logPath: string, chunk: string): Promise<void> {
  await appendFile(logPath, chunk, 'utf-8');
}

async function updateRunJson(
  runId: string,
  patch: { status?: string; currentStep?: string; error?: string | null; finished?: boolean },
): Promise<void> {
  const file = path.join(getBackendRoot(), 'agents', 'pipeline', 'runs', runId, 'run.json');
  try {
    const data = JSON.parse(await readFile(file, 'utf-8')) as Record<string, unknown>;
    if (patch.status) {
      data.status = patch.status;
      if (['completed', 'failed', 'cancelled'].includes(patch.status)) {
        data.finishedAt = new Date().toISOString();
      }
      if (patch.status === 'completed') {
        data.currentStep = null;
        const steps = data.steps as Array<{ name: string; status?: string }> | undefined;
        if (steps) {
          for (const step of steps) {
            if (step.status !== 'skipped') step.status = 'completed';
          }
        }
      } else if (patch.status === 'failed' || patch.status === 'cancelled') {
        // Mark the in-flight step failed too - otherwise it stays "running" forever in
        // the steps array (set by an earlier currentStep update) even though the top-level
        // status is terminal, and the UI's step timeline shows a phantom live step.
        const steps = data.steps as Array<{ name: string; status?: string }> | undefined;
        if (steps) {
          for (const step of steps) {
            if (step.status === 'running') step.status = patch.status;
          }
        }
      }
    }
    if (patch.currentStep) {
      data.currentStep = patch.currentStep;
      const steps = data.steps as Array<{ name: string; status?: string }> | undefined;
      if (steps) {
        for (const step of steps) {
          if (step.name === patch.currentStep) step.status = 'running';
          else if (step.status === 'running') step.status = 'completed';
        }
      }
    }
    if (patch.error !== undefined) data.error = patch.error;
    else if (patch.status === 'completed') data.error = null;
    await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf-8');
  } catch {
    // run.json is best-effort for UI
  }
}

async function gitlabPublished(runId: string, app: string): Promise<boolean> {
  return gitlabPublishSucceededForRun(runId, app);
}

export async function finalizeRunJson(
  runId: string,
  patch: { status?: string; currentStep?: string; error?: string | null; finished?: boolean },
): Promise<void> {
  await updateRunJson(runId, patch);
  invalidateRunsCache();
}

function envInt(name: string, fallback: number): number {
  const parsed = parseInt(process.env[name] ?? '', 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function envBool(name: string, fallback = false): boolean {
  const raw = (process.env[name] ?? '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(raw)) return true;
  if (['0', 'false', 'no', 'off'].includes(raw)) return false;
  return fallback;
}

function developerFallbackModel(): string {
  const raw = process.env.DEVELOPER_AGENT_FALLBACK_MODEL_ID;
  if (raw === undefined) return DEFAULT_DEVELOPER_FALLBACK_MODEL;
  return raw.trim();
}

/**
 * Invoke developer-agent directly (bypasses orchestrator) with the Sonnet fallback so
 * a killed orchestrator session cannot leave the run stuck at status="in_progress".
 * Returns true when the resulting developer handoff reaches status=completed.
 */
async function invokeDeveloperFallback(
  runId: string,
  app: string,
  logPath: string,
  timeoutSec: number,
  attempt: number,
  totalAttempts: number,
  skipDb: boolean,
): Promise<boolean> {
  await updateRunJson(runId, { currentStep: 'developer-agent' });
  const fallbackModel = developerFallbackModel();
  const baseTask = skipDb ? DEV_TASK_NO_DB : DEV_TASK_DB;
  const task =
    `${baseTask}\n\nRETRY NOTE: a previous developer-agent attempt did not reach a ` +
    `completed handoff. Re-implement the app end-to-end and ensure the developer ` +
    `handoff status is "completed" before returning.\n\n` +
    `Context:\n${JSON.stringify(
      {
        targetApp: app,
        runId,
        ...(fallbackModel ? { codingModelOverride: fallbackModel } : {}),
      },
      null,
      2,
    )}`;

  await appendLog(
    logPath,
    `[dev-fallback] Invoking developer-agent directly (attempt ${attempt}/${totalAttempts}` +
      `${fallbackModel ? `, model=${fallbackModel}` : ''}).\n`,
  );

  const result = await invokeAgentRuntimeA2a('developer-agent', task, { timeoutSec });
  await appendLog(logPath, `[dev-fallback] status: ${result.status}\n`);
  if (result.error) await appendLog(logPath, `[dev-fallback] error: ${result.error}\n`);
  if (result.text) {
    await appendLog(logPath, `[dev-fallback] response: ${result.text.slice(0, 1500)}\n`);
  }

  const handoffWaitSec = envInt('SDLC_DEV_FALLBACK_HANDOFF_WAIT_SEC', 900);
  const ready = await waitForDeveloperHandoffForRun(runId, app, { timeoutSec: handoffWaitSec });
  await appendLog(
    logPath,
    `[dev-fallback] handoff status after wait: ${ready ? 'completed' : 'not completed'}\n`,
  );
  return ready;
}

async function invokeGitlabFallback(
  runId: string,
  app: string,
  logPath: string,
  timeoutSec: number,
): Promise<void> {
  await updateRunJson(runId, { currentStep: 'gitlab-agent' });
  const glTask =
    `Publish SDLC artifacts for ${app} to GitLab branch sdlc/${app}.\n\n` +
    `Context:\n${JSON.stringify({ targetApp: app, runId }, null, 2)}`;
  // Publish is idempotent (same branch/artifacts), so retry transient gitlab-agent failures.
  const maxAttempts = envInt('SDLC_GITLAB_PUBLISH_RETRIES', 2) + 1;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    await appendLog(
      logPath,
      `[gitlab-fallback] Invoking gitlab-agent on AgentCore (attempt ${attempt}/${maxAttempts})...\n`,
    );
    const glResult = await invokeAgentRuntimeA2a('gitlab-agent', glTask, { timeoutSec });
    await appendLog(logPath, `[gitlab-fallback] cloud status: ${glResult.status}\n`);
    if (glResult.error) await appendLog(logPath, `[gitlab-fallback] cloud error: ${glResult.error}\n`);
    if (glResult.text) {
      await appendLog(logPath, `[gitlab-fallback] cloud response: ${glResult.text.slice(0, 1500)}\n`);
    }
    if (glResult.status === 'success' && (await gitlabPublished(runId, app))) {
      await appendLog(logPath, '[gitlab-fallback] Cloud gitlab-agent succeeded.\n');
      return;
    }
    if (attempt < maxAttempts) {
      await appendLog(logPath, '[gitlab-fallback] Publish not confirmed - retrying...\n');
    }
  }
  await appendLog(
    logPath,
    '[gitlab-fallback] Cloud gitlab-agent failed or no handoff - artifacts remain in S3.\n',
  );
}

interface RunStatusDoc {
  status?: unknown;
  currentStep?: unknown;
  error?: unknown;
}

/**
 * Poll the orchestrator's S3 run.json mirror until it reports a terminal state.
 * This is the primary completion signal for async (fire-and-forget) orchestrator
 * runs; the AgentCore invoke itself only returns a "PIPELINE_ASYNC_STARTED" ack.
 * Mirrors currentStep into the local run.json so the UI live-updates while polling.
 */
async function pollRunStatusUntilTerminal(
  runId: string,
  logPath: string,
  timeoutSec: number,
): Promise<{ status: 'completed' | 'failed' | 'timeout'; error?: string | null }> {
  const pollMs = Math.max(2000, envInt('SDLC_PIPELINE_STATUS_POLL_MS', 15000));
  const deadline = Date.now() + timeoutSec * 1000;
  let lastStep: string | null = null;
  let lastStatus = '';

  while (Date.now() < deadline) {
    const doc = (await getRunArtifactJson(runId, 'run.json')) as RunStatusDoc | null;
    if (doc) {
      const status = typeof doc.status === 'string' ? doc.status.toLowerCase() : '';
      const step = typeof doc.currentStep === 'string' ? doc.currentStep : null;
      if (step && step !== lastStep) {
        lastStep = step;
        await appendLog(logPath, `[status-poll] currentStep: ${step}\n`);
        await updateRunJson(runId, { currentStep: step });
        invalidateRunsCache();
      }
      if (status && status !== lastStatus) {
        lastStatus = status;
        await appendLog(logPath, `[status-poll] status: ${status}\n`);
      }
      if (status === 'completed') return { status: 'completed' };
      if (status === 'failed' || status === 'cancelled') {
        return {
          status: 'failed',
          error: typeof doc.error === 'string' ? doc.error : null,
        };
      }
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  return { status: 'timeout' };
}

export interface RunOrchestratorCloudOptions extends PipelineTaskOptions {
  logPath: string;
  timeoutSec: number;
}

/**
 * Invoke orchestrator-agent on AgentCore (AWS SDK) and optional cloud gitlab-agent fallback.
 * No local Python subprocess - only the AgentCore runtimes execute the pipeline.
 */
export async function runOrchestratorCloud(options: RunOrchestratorCloudOptions): Promise<void> {
  const { logPath, timeoutSec, ...taskOpts } = options;
  const app = taskOpts.targetApp;
  const runId = taskOpts.runId;

  await mkdir(path.dirname(logPath), { recursive: true });

  const task = buildOrchestratorTask(taskOpts);
  await appendLog(logPath, `Invoking orchestrator-agent (AgentCore SDK, no local Python)...\n${task}\n`);
  if (!taskOpts.skipPostgres && !taskOpts.skipDb) {
    await appendLog(
      logPath,
      'Note: skip_postgres=false - orchestrator applies RDS in-cloud after database-agent.\n---\n',
    );
  }

  if (!taskOpts.skipGitlab) {
    await updateRunJson(runId, { status: 'running', currentStep: 'product-agent' });
  }

  const result = await invokeAgentRuntimeA2a('orchestrator-agent', task, { timeoutSec });
  await appendLog(logPath, `status: ${result.status}\n`);
  if (result.error) await appendLog(logPath, `error: ${result.error}\n`);
  const text = result.text ?? '';
  await appendLog(logPath, `--- response ---\n${text.slice(0, 8000)}\n`);

  // Async orchestrator: the invoke returns an ack in seconds and the pipeline
  // keeps running in the cloud. Poll the S3 run.json mirror to the terminal
  // state; only fall through to the legacy fallback chain on poll timeout or
  // when a "completed" claim cannot be verified against the publish handoff.
  const asyncStarted = result.status === 'success' && text.includes('PIPELINE_ASYNC_STARTED');
  if (asyncStarted) {
    const statusWaitSec = envInt('SDLC_PIPELINE_STATUS_WAIT_SEC', 7200);
    await appendLog(
      logPath,
      `[status-poll] Async orchestrator accepted; polling runs/${runId}/run.json (timeout=${statusWaitSec}s)...\n`,
    );
    const final = await pollRunStatusUntilTerminal(runId, logPath, statusWaitSec);
    if (final.status === 'completed') {
      if (taskOpts.skipGitlab || (await gitlabPublished(runId, app))) {
        await appendLog(logPath, '[status-poll] Pipeline completed in cloud.\n');
        await finalizeRunJson(runId, { status: 'completed' });
        return;
      }
      await appendLog(
        logPath,
        '[status-poll] Orchestrator reports completed but no GitLab publish handoff found - running fallback verification.\n',
      );
    } else if (final.status === 'failed') {
      // "SDLC pipeline failed" is one of parseLogTerminalStatus's recognized markers
      // (run-reconcile.ts) - without it, a reconciler pass driven only by log text (no
      // run.json) can't tell this run apart from one still in progress.
      await appendLog(
        logPath,
        `[status-poll] SDLC pipeline failed: ${final.error ?? 'unknown error'}\n`,
      );
      await finalizeRunJson(runId, {
        status: 'failed',
        error: final.error ?? 'pipeline failed in cloud - check CloudWatch orchestrator logs',
      });
      return;
    } else {
      await appendLog(
        logPath,
        '[status-poll] Timed out waiting for terminal run status - entering fallback verification path.\n',
      );
    }
  }

  let developerCompleted = false;
  if (!taskOpts.skipGitlab) {
    await appendLog(logPath, '--- gitlab ---\n');
    if (await gitlabPublished(runId, app)) {
      await appendLog(logPath, '[gitlab] Publish succeeded (orchestrator). Skipping fallback.\n');
      developerCompleted = true;
    } else if (!taskOpts.skipDeveloper) {
      await appendLog(logPath, '[gitlab-fallback] Waiting for developer output before publish...\n');
      const handoffWaitSec = Math.min(timeoutSec, envInt('SDLC_GITLAB_FALLBACK_HANDOFF_WAIT_SEC', 900));
      developerCompleted = await waitForDeveloperHandoffForRun(runId, app, {
        timeoutSec: handoffWaitSec,
      });

      // If orchestrator's own retry loop got killed with its session, the frontend
      // re-invokes developer-agent here so a stuck status="in_progress" handoff cannot
      // silently masquerade as success (and cannot get partial code published to GitLab).
      const maxFrontendAttempts = envInt('SDLC_DEVELOPER_FRONTEND_RETRY_ATTEMPTS', 1) + 1;
      let attempt = 1;
      while (!developerCompleted && attempt <= maxFrontendAttempts) {
        const status = await developerHandoffSucceededForRun(runId, app);
        await appendLog(
          logPath,
          `[dev-fallback] Handoff not completed after wait (succeeded=${status}); re-invoking developer-agent.\n`,
        );
        developerCompleted = await invokeDeveloperFallback(
          runId,
          app,
          logPath,
          timeoutSec,
          attempt,
          maxFrontendAttempts,
          taskOpts.skipDb ?? false,
        );
        attempt += 1;
      }

      if (developerCompleted) {
        await invokeGitlabFallback(runId, app, logPath, timeoutSec);
      } else {
        const allowPartial = envBool('SDLC_ALLOW_PARTIAL_PUBLISH', false);
        const hasAppCode = await s3RunHasAppCode(runId);
        if (allowPartial && hasAppCode) {
          await appendLog(
            logPath,
            '[gitlab-fallback] developer handoff not completed but SDLC_ALLOW_PARTIAL_PUBLISH=true — publishing anyway.\n',
          );
          await invokeGitlabFallback(runId, app, logPath, timeoutSec);
        } else {
          await appendLog(
            logPath,
            '[gitlab-fallback] developer-agent did not reach a completed handoff after retries — NOT publishing partial code to GitLab.\n',
          );
        }
      }
    } else {
      // skipDeveloper=true — orchestrator/gitlab-agent already covered by prior branch.
      await invokeGitlabFallback(runId, app, logPath, timeoutSec);
      developerCompleted = true;
    }
  }

  const textLower = text.toLowerCase();
  const orchestratorOk = result.status === 'success' && !textLower.includes('pipeline failed');
  const gitlabDidPublish = !taskOpts.skipGitlab && (await gitlabPublished(runId, app));

  // A run is only truly complete when GitLab published (or GitLab was skipped and the
  // orchestrator succeeded). Otherwise report the real failure instead of a false green
  // pipeline that masks a developer/gitlab step that produced nothing.
  if (taskOpts.skipGitlab) {
    if (orchestratorOk) {
      await finalizeRunJson(runId, { status: 'completed' });
    } else {
      const isTimeout = /timeout|timed.?out/i.test(result.error ?? '');
      await finalizeRunJson(runId, {
        status: 'failed',
        error: isTimeout
          ? 'Orchestrator HTTP timeout - pipeline may still be running in cloud (check CloudWatch)'
          : (result.error ?? 'orchestrator did not complete - check CloudWatch logs'),
      });
    }
    return;
  }

  if (gitlabDidPublish && developerCompleted) {
    await finalizeRunJson(runId, { status: 'completed' });
  } else if (!developerCompleted) {
    await finalizeRunJson(runId, {
      status: 'failed',
      error:
        'developer-agent did not reach a completed handoff after retries - partial app code was NOT published to GitLab (check CloudWatch developer_agent logs)',
    });
  } else if (await s3RunHasAppCode(runId)) {
    await finalizeRunJson(runId, {
      status: 'failed',
      error:
        'App code was generated but GitLab publish did not complete - artifacts remain in S3 (check gitlab-agent / CloudWatch)',
    });
  } else {
    const isTimeout = /timeout|timed.?out/i.test(result.error ?? '');
    await finalizeRunJson(runId, {
      status: 'failed',
      error: isTimeout
        ? 'Developer/GitLab step timed out - no app code was published (check CloudWatch)'
        : (result.error ?? 'Pipeline stopped before publishing app code - check CloudWatch logs'),
    });
  }
}
