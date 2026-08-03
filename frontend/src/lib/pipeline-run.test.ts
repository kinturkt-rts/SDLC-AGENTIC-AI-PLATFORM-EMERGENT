import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { ExistingProjectConflictError, summarizeExistingProject } from './pipeline-run';

describe('summarizeExistingProject', () => {
  it('returns null when the slug has never been used', () => {
    const runs = [
      { projectId: 'other-app', startedAt: '2026-07-01T00:00:00.000Z', status: 'completed' },
    ];
    assert.equal(summarizeExistingProject(runs, 'ai-ops-assist'), null);
  });

  it('summarizes run count and first/last-seen timestamps across multiple runs for the slug', () => {
    const runs = [
      { projectId: 'ai-ops-assist', startedAt: '2026-07-01T00:00:00.000Z', status: 'failed' },
      { projectId: 'other-app', startedAt: '2026-07-02T00:00:00.000Z', status: 'completed' },
      { projectId: 'ai-ops-assist', startedAt: '2026-07-15T00:00:00.000Z', status: 'completed' },
      { projectId: 'ai-ops-assist', startedAt: '2026-07-10T00:00:00.000Z', status: 'running' },
    ];
    const result = summarizeExistingProject(runs, 'ai-ops-assist');
    assert.ok(result);
    assert.equal(result.runCount, 3);
    assert.equal(result.firstSeenAt, '2026-07-01T00:00:00.000Z');
    assert.equal(result.lastRunAt, '2026-07-15T00:00:00.000Z');
    assert.equal(result.lastRunStatus, 'completed');
  });

  it('reports a single prior run correctly (runCount 1)', () => {
    const runs = [
      { projectId: 'notice-board-ui', startedAt: '2026-06-01T00:00:00.000Z', status: 'awaiting_deploy' },
    ];
    const result = summarizeExistingProject(runs, 'notice-board-ui');
    assert.ok(result);
    assert.equal(result.runCount, 1);
    assert.equal(result.firstSeenAt, result.lastRunAt);
    assert.equal(result.lastRunStatus, 'awaiting_deploy');
  });
});

describe('ExistingProjectConflictError', () => {
  it('pluralizes "runs" correctly and carries the project info through', () => {
    const info = {
      projectId: 'ai-ops-assist',
      runCount: 3,
      firstSeenAt: '2026-07-01T00:00:00.000Z',
      lastRunAt: '2026-07-15T00:00:00.000Z',
      lastRunStatus: 'completed',
    };
    const err = new ExistingProjectConflictError(info);
    assert.equal(err.project, info);
    assert.match(err.message, /"ai-ops-assist" already exists \(3 previous runs, last completed\)/);
  });

  it('does not pluralize for exactly one prior run', () => {
    const info = {
      projectId: 'notice-board-ui',
      runCount: 1,
      firstSeenAt: '2026-06-01T00:00:00.000Z',
      lastRunAt: '2026-06-01T00:00:00.000Z',
      lastRunStatus: 'failed',
    };
    const err = new ExistingProjectConflictError(info);
    assert.match(err.message, /"notice-board-ui" already exists \(1 previous run, last failed\)/);
  });
});
