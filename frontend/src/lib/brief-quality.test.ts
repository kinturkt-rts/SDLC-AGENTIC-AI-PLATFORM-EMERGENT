import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { validateProductBrief } from './brief-quality';

describe('validateProductBrief', () => {
  it('rejects empty and mash', () => {
    assert.ok(validateProductBrief(''));
    assert.ok(validateProductBrief('hjh'));
    assert.ok(validateProductBrief('jhj'));
    assert.ok(validateProductBrief('!!!@@@###'));
  });

  it('accepts a real sample input brief', () => {
    const sample = readFileSync(
      path.join(process.cwd(), '..', 'backend', 'inputs', 'checkout.txt'),
      'utf-8',
    );
    assert.equal(validateProductBrief(sample), null);
  });
});
