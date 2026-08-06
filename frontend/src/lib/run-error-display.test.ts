import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { parseRunValidationError } from './run-error-display';

const SCHEMA_PARITY_ERROR = [
  'developer-agent validation failed:',
  'Validation failed at schema_parity:',
  'SCHEMA_PARITY FAILED (applied DB vs ORM models):',
  "  - schema_parity: shifts.required_certs type category mismatch — DB is 'array' but ORM maps to 'string'",
  "  - schema_parity: shifts.required_skills type category mismatch — DB is 'array' but ORM maps to 'string'",
  "  - schema_parity: volunteers.skills type category mismatch — DB is 'array' but ORM maps to 'string'",
  'Passed before failure: deps, structure, syntax, py_encodable, env_example, router_antipattern, duplicate_action_route, conftest, rds_parity, users_auth_columns, main_registers_auth, main_registers_me, cors_configured, relationship_secondary, auth_mode_files',
  '',
  'VALIDATION FAILED — fix all errors above and call dev_validate_app again.',
].join('\n');

describe('parseRunValidationError', () => {
  it('extracts agent, step, and clean bullets from a real schema_parity failure', () => {
    const parsed = parseRunValidationError(SCHEMA_PARITY_ERROR);
    assert.ok(parsed);
    assert.equal(parsed?.agent, 'developer-agent');
    assert.equal(parsed?.step, 'schema_parity');
    assert.equal(parsed?.bullets.length, 3);
    // Redundant "schema_parity: " prefix stripped from every bullet.
    assert.equal(
      parsed?.bullets[0],
      "shifts.required_certs type category mismatch — DB is 'array' but ORM maps to 'string'",
    );
    // Tool bookkeeping never leaks into the human-facing bullets.
    assert.ok(!parsed?.bullets.some((b) => b.includes('Passed before failure')));
    assert.ok(!parsed?.bullets.some((b) => b.includes('VALIDATION FAILED')));
    assert.match(parsed!.summary, /schema_parity/);
    assert.match(parsed!.summary, /3 issues/);
  });

  it('returns null for an unstructured error (falls back to raw display)', () => {
    assert.equal(parseRunValidationError('Connection timed out'), null);
    assert.equal(parseRunValidationError(null), null);
    assert.equal(parseRunValidationError(undefined), null);
  });
});
