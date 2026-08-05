import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  DEPLOY_STALE_MS,
  isDeployStale,
  reconcileRunStatus,
  resolveDisplayStatus,
} from './run-reconcile';
import type { SdlcPhase } from '@/src/types';

const allDone: Record<SdlcPhase, boolean> = {
  requirements: true,
  architecture: true,
  data: true,
  implementation: true,
  frontend: true,
  qa: false,
  security: false,
  publish: true,
  deploy: false,
};

const emptyPhases: Record<SdlcPhase, boolean> = {
  requirements: false,
  architecture: false,
  data: false,
  implementation: false,
  frontend: false,
  qa: false,
  security: false,
  publish: false,
  deploy: false,
};

describe('reconcileRunStatus', () => {
  it('keeps cancelled even when every pipeline phase has artifacts', () => {
    const result = reconcileRunStatus({
      status: 'cancelled',
      startedAt: new Date(Date.now() - 60_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: 'SDLC pipeline completed\n',
      phaseDone: allDone,
      error: 'Cancelled by user',
    });

    assert.equal(result.status, 'cancelled');
    assert.equal(result.currentStep, null);
    assert.equal(result.error, 'Cancelled by user');
  });

  it('keeps cancelled when logs claim success but phases are incomplete', () => {
    const result = reconcileRunStatus({
      status: 'cancelled',
      startedAt: new Date(Date.now() - 60_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: 0,
      logText: '[gitlab-fallback] cloud gitlab-agent succeeded\n',
      phaseDone: {
        ...allDone,
        publish: false,
        implementation: false,
      },
      error: 'Cancelled by user',
    });

    assert.equal(result.status, 'cancelled');
  });

  it('prefers reportedCurrentStep when artifact index lags behind live progress', () => {
    const result = reconcileRunStatus({
      status: 'running',
      startedAt: new Date(Date.now() - 60_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: '[developer-agent] running\n',
      phaseDone: {
        requirements: true,
        architecture: false,
        data: false,
        implementation: false,
        frontend: false,
        qa: false,
        security: false,
        publish: false,
        deploy: false,
      },
      reportedCurrentStep: 'developer-agent',
    });

    assert.equal(result.status, 'running');
    assert.equal(result.currentStep, 'developer-agent');
  });

  it('Phase A: completed after publish even when deploy is pending', () => {
    const result = reconcileRunStatus({
      status: 'completed',
      startedAt: new Date(Date.now() - 600_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: 'SDLC pipeline completed\n',
      phaseDone: { ...allDone, deploy: false },
    });

    // Status must remain completed — deploy is follow-on, not a blocker.
    assert.equal(result.status, 'completed');
    assert.equal(result.currentStep, null);
  });

  it('Phase A: completed stays completed even with deploy done', () => {
    const result = reconcileRunStatus({
      status: 'completed',
      startedAt: new Date(Date.now() - 900_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: 'SDLC pipeline completed\n',
      phaseDone: { ...allDone, deploy: true },
    });

    assert.equal(result.status, 'completed');
  });

  it('operator-marked failed stays failed even when every authoring artifact exists', () => {
    // Regression: verifiedComplete used to upgrade failed → completed, then deploy UX
    // remapped that to running — restaurant/subscription stayed "Running" after mark-failed.
    const result = reconcileRunStatus({
      status: 'failed',
      startedAt: new Date(Date.now() - 900_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: 'SDLC pipeline failed\n',
      phaseDone: allDone,
      error: 'Marked failed by operator (deploy stuck / abandoned).',
    });

    assert.equal(result.status, 'failed');
    assert.match(result.error ?? '', /Marked failed by operator/);
  });

  it('names the phase that never finished instead of a blanket message when the error is generic', () => {
    // Regression: orchestrator crashed between database-agent and developer-agent
    // (no exception ever caught, so run.json got no specific error) — the dashboard
    // showed "SDLC pipeline failed" with no indication developer-agent never started.
    const result = reconcileRunStatus({
      status: 'failed',
      startedAt: new Date(Date.now() - 300_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: null,
      phaseDone: { ...emptyPhases, requirements: true, architecture: true, data: true },
      error: 'SDLC pipeline failed',
    });

    assert.equal(result.status, 'failed');
    assert.equal(result.currentStep, 'developer-agent');
    assert.match(result.error ?? '', /Developer-agent/);
  });

  it('keeps a specific error message as-is rather than overriding it with a phase guess', () => {
    const result = reconcileRunStatus({
      status: 'failed',
      startedAt: new Date(Date.now() - 300_000).toISOString(),
      logMtimeMs: Date.now(),
      s3MtimeMs: Date.now(),
      logText: null,
      phaseDone: { ...emptyPhases, requirements: true, architecture: true, data: true },
      error: 'Database migration 004_add_index.sql failed: relation already exists',
    });

    assert.match(result.error ?? '', /004_add_index\.sql/);
  });

  it('awaiting_deploy with evidence stays awaiting_deploy after the idle window', () => {
    const startedAt = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    const result = reconcileRunStatus({
      status: 'awaiting_deploy',
      startedAt,
      logMtimeMs: 0,
      s3MtimeMs: Date.parse(startedAt) + 20 * 60 * 1000,
      logText: null,
      phaseDone: allDone,
      reportedCurrentStep: 'gitlab-agent',
    });

    assert.equal(result.status, 'awaiting_deploy');
    assert.equal(result.currentStep, 'devops-agent');
  });

  it('never reports "never completed product-agent" for a run that reached a later step', () => {
    const startedAt = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    const result = reconcileRunStatus({
      status: 'awaiting_deploy',
      startedAt,
      logMtimeMs: 0,
      s3MtimeMs: 0,
      logText: null,
      phaseDone: emptyPhases,
      reportedCurrentStep: 'gitlab-agent',
    });

    assert.equal(result.status, 'failed');
    assert.match(result.error ?? '', /gitlab-agent/);
    assert.doesNotMatch(result.error ?? '', /never completed product-agent/);
  });
});

describe('isDeployStale', () => {
  const now = Date.now();
  const old = now - (DEPLOY_STALE_MS + 60_000);

  it('is false once the deploy succeeded, however old the run is', () => {
    assert.equal(
      isDeployStale({ isTerminalForDeploy: true, deploySucceeded: true, s3MtimeMs: old, now }),
      false,
    );
  });

  it('is true when publish is terminal but no live URL ever appeared', () => {
    assert.equal(
      isDeployStale({ isTerminalForDeploy: true, deploySucceeded: false, s3MtimeMs: old, now }),
      true,
    );
  });

  it('is false inside the deploy window', () => {
    assert.equal(
      isDeployStale({
        isTerminalForDeploy: true,
        deploySucceeded: false,
        s3MtimeMs: now - 60_000,
        now,
      }),
      false,
    );
  });

  it('is false when the run is still mid-pipeline', () => {
    assert.equal(
      isDeployStale({ isTerminalForDeploy: false, deploySucceeded: false, s3MtimeMs: old, now }),
      false,
    );
  });

  it('is false when no artifact timestamp is known', () => {
    assert.equal(
      isDeployStale({ isTerminalForDeploy: true, deploySucceeded: false, s3MtimeMs: 0, now }),
      false,
    );
  });
});

describe('resolveDisplayStatus', () => {
  const base = {
    reconciledStatus: 'awaiting_deploy' as const,
    deploySucceeded: false,
    deployCiFailed: false,
    deployIsStale: false,
    deployStepFailed: false,
    deployStepRunning: false,
  };

  it('regression: a live app stays completed even when stale/failed signals are set', () => {
    // Every run older than 30 minutes used to be reported Failed on the Pipeline Runs
    // page despite a healthy live URL, because stale was checked before success.
    assert.equal(
      resolveDisplayStatus({
        ...base,
        deploySucceeded: true,
        deployIsStale: true,
        deployStepFailed: true,
        deployCiFailed: true,
      }),
      'completed',
    );
  });

  it('reports failed when CI failed and no live URL exists', () => {
    assert.equal(resolveDisplayStatus({ ...base, deployCiFailed: true }), 'failed');
  });

  it('reports failed when publish never produced a deploy', () => {
    assert.equal(resolveDisplayStatus({ ...base, deployIsStale: true }), 'failed');
  });

  it('keeps awaiting_deploy while CI is still in flight', () => {
    assert.equal(resolveDisplayStatus(base), 'awaiting_deploy');
  });

  it('keeps the run live on Deploy after AgentCore marks it completed', () => {
    assert.equal(
      resolveDisplayStatus({
        ...base,
        reconciledStatus: 'completed',
        deployStepRunning: true,
      }),
      'running',
    );
  });

  it('passes through terminal reconciled statuses', () => {
    assert.equal(resolveDisplayStatus({ ...base, reconciledStatus: 'cancelled' }), 'cancelled');
    assert.equal(resolveDisplayStatus({ ...base, reconciledStatus: 'failed' }), 'failed');
  });
});
