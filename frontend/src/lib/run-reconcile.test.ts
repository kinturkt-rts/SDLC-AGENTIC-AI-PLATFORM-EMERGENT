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
});
