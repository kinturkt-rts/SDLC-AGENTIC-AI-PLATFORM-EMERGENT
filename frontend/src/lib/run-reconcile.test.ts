import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { reconcileRunStatus } from './run-reconcile';
import type { SdlcPhase } from '@/src/types';

const allDone: Record<SdlcPhase, boolean> = {
  requirements: true,
  architecture: true,
  data: true,
  implementation: true,
  qa: false,
  security: false,
  publish: true,
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
});
