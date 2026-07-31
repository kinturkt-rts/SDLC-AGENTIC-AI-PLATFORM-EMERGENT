import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { applyCurrentStepPhaseOverride } from './repo-reader';
import type { SdlcPhase } from '@/src/types';

const emptyPhases: Record<SdlcPhase, boolean> = {
  requirements: false,
  architecture: false,
  data: false,
  implementation: false,
  qa: false,
  security: false,
  publish: false,
  deploy: false,
};

describe('applyCurrentStepPhaseOverride', () => {
  it('regression: rds-apply failing pins blame on Database, not an unrelated earlier phase', () => {
    // Simulates the employee-leave-manager incident: architecture's own artifact
    // check happened to read "not done" for this run (phaseDone.architecture is
    // false), but the backend's last-recorded step is database-agent (rds-apply
    // runs after it and never updates currentStep). The failure must be pinned to
    // "data" (Database), and architecture must be marked done since a real, earlier
    // step genuinely ran to completion before the actual failure point.
    const phaseDone = { ...emptyPhases };
    const result = applyCurrentStepPhaseOverride(phaseDone, 'database-agent', 'failed');

    assert.equal(result.requirements, true);
    assert.equal(result.architecture, true);
    assert.equal(result.data, false);
  });

  it('marks every phase strictly before currentStep as done on a failed run', () => {
    const phaseDone = { ...emptyPhases };
    const result = applyCurrentStepPhaseOverride(phaseDone, 'developer-agent', 'failed');

    assert.equal(result.requirements, true);
    assert.equal(result.architecture, true);
    assert.equal(result.data, true);
    assert.equal(result.implementation, false); // currentStep's own phase — pinned as the failure point
  });

  it('does not force phaseDone false on a running (non-terminal) status', () => {
    const phaseDone = { ...emptyPhases, data: true };
    const result = applyCurrentStepPhaseOverride(phaseDone, 'developer-agent', 'running');

    // Earlier phases still get marked done so the strip doesn't flash an older agent...
    assert.equal(result.architecture, true);
    // ...but the current phase is left alone (still whatever phaseDone said), since
    // "running" isn't a failure and there's nothing to pin blame on.
    assert.equal(result.implementation, false);
  });

  it('is a no-op when currentStep is unknown or status is not running/failed', () => {
    const phaseDone = { ...emptyPhases, architecture: true };
    assert.deepEqual(
      applyCurrentStepPhaseOverride(phaseDone, null, 'failed'),
      phaseDone,
    );
    assert.deepEqual(
      applyCurrentStepPhaseOverride(phaseDone, 'developer-agent', 'completed'),
      phaseDone,
    );
    assert.deepEqual(
      applyCurrentStepPhaseOverride(phaseDone, 'not-a-real-agent', 'failed'),
      phaseDone,
    );
  });
});
