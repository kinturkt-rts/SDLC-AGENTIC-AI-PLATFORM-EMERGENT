import { appendFile, readFile, writeFile, mkdir } from 'fs/promises';
import path from 'path';
import { getBackendRoot } from './repo-root';
import { invalidateRunsCache } from './runs-cache';
import {
  gitlabPublishSucceededForRun,
  waitForDeveloperHandoffForRun,
} from './pipeline-handoffs';
import { invokeAgentRuntimeA2a } from './agentcore-invoke';
import { s3RunHasAppCode } from './artifact-store';

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

async function finalizeRunJson(
  runId: string,
  patch: { status?: string; currentStep?: string; error?: string | null; finished?: boolean },
): Promise<void> {
  await updateRunJson(runId, patch);
  invalidateRunsCache();
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
  await appendLog(logPath, '[gitlab-fallback] Invoking gitlab-agent on AgentCore...\n');
  const glResult = await invokeAgentRuntimeA2a('gitlab-agent', glTask, { timeoutSec });
  await appendLog(logPath, `[gitlab-fallback] cloud status: ${glResult.status}\n`);
  if (glResult.error) await appendLog(logPath, `[gitlab-fallback] cloud error: ${glResult.error}\n`);
  if (glResult.text) {
    await appendLog(logPath, `[gitlab-fallback] cloud response: ${glResult.text.slice(0, 1500)}\n`);
  }
  if (glResult.status === 'success' && (await gitlabPublished(runId, app))) {
    await appendLog(logPath, '[gitlab-fallback] Cloud gitlab-agent succeeded.\n');
  } else {
    await appendLog(
      logPath,
      '[gitlab-fallback] Cloud gitlab-agent failed or no handoff - artifacts remain in S3.\n',
    );
  }
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

  if (!taskOpts.skipGitlab) {
    await appendLog(logPath, '--- gitlab ---\n');
    if (await gitlabPublished(runId, app)) {
      await appendLog(logPath, '[gitlab] Publish succeeded (orchestrator). Skipping fallback.\n');
    } else if (!taskOpts.skipDeveloper) {
      await appendLog(logPath, '[gitlab-fallback] Waiting for developer output before publish...\n');
      // Handoff is written last and can be lost to a developer-agent timeout kill, so also
      // accept app code that already landed in S3 as proof the developer produced output.
      const handoffWaitSec = Math.min(timeoutSec, 180);
      const devReady = await waitForDeveloperHandoffForRun(runId, app, {
        timeoutSec: handoffWaitSec,
      });
      const hasAppCode = devReady || (await s3RunHasAppCode(runId));
      if (hasAppCode) {
        if (!devReady) {
          await appendLog(
            logPath,
            '[gitlab-fallback] developer-handoff missing but app code is in S3 — publishing anyway.\n',
          );
        }
        await invokeGitlabFallback(runId, app, logPath, timeoutSec);
      } else {
        await appendLog(
          logPath,
          '[gitlab-fallback] no developer output in S3 — skipping GitLab publish (developer-agent produced no app code).\n',
        );
      }
    } else {
      await invokeGitlabFallback(runId, app, logPath, timeoutSec);
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

  if (gitlabDidPublish) {
    await finalizeRunJson(runId, { status: 'completed' });
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
