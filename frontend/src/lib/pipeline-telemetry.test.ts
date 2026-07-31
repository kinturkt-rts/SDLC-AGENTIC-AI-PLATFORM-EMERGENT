import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { computeDeployTiming } from './pipeline-telemetry';

const startMs = Date.parse('2026-07-29T10:00:00.000Z');

describe('computeDeployTiming', () => {
  it('measures live deploy time from publish handoff to the deployedAt timestamp', () => {
    const result = computeDeployTiming(
      startMs,
      { appUrl: 'https://example.com', deployedAt: '2026-07-29T10:12:30.000Z', status: 'healthy', healthy: true },
      startMs + 999_999,
    );
    assert.deepEqual(result, { deploySec: 750, deployStatus: 'live' });
  });

  it('reports deploying with a live-ticking duration while there is no app URL yet', () => {
    const nowMs = startMs + 5 * 60_000;
    const result = computeDeployTiming(startMs, { status: 'in_progress' }, nowMs);
    assert.deepEqual(result, { deploySec: 300, deployStatus: 'deploying' });
  });

  it('reports failed when the health check explicitly failed', () => {
    const nowMs = startMs + 60_000;
    const result = computeDeployTiming(startMs, { status: 'deployed', healthy: false }, nowMs);
    assert.deepEqual(result, { deploySec: 60, deployStatus: 'failed' });
  });

  it('reports failed when status is failed even without an explicit healthy flag', () => {
    const nowMs = startMs + 60_000;
    const result = computeDeployTiming(startMs, { status: 'failed' }, nowMs);
    assert.equal(result.deployStatus, 'failed');
  });
});
