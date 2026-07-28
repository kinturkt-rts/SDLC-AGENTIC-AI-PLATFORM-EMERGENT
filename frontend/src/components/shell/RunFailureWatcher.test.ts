import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { summarizeRunError } from './RunFailureWatcher';

describe('summarizeRunError', () => {
  it('returns short single-line errors unchanged', () => {
    assert.equal(summarizeRunError('Cloud orchestrator invoke failed'), 'Cloud orchestrator invoke failed');
  });

  it('takes only the first line of a multi-paragraph subprocess dump', () => {
    const raw =
      "rds-apply failed (exit 1): AWS_PROFILE=(not set) AWS_REGION=us-east-2\n" +
      "Caller: arn:aws:sts::061836593297:assumed-role/...\n" +
      'Applying 011_seed.sql ... FAILED: relation "departments" does not exist\n';
    const result = summarizeRunError(raw);
    assert.ok(!result.includes('\n'));
    assert.ok(result.startsWith('rds-apply failed (exit 1):'));
  });

  it('truncates an overly long single line with an ellipsis', () => {
    const raw = 'FAILED: ' + 'x'.repeat(300);
    const result = summarizeRunError(raw);
    assert.ok(result.length <= 160);
    assert.ok(result.endsWith('…'));
  });
});
