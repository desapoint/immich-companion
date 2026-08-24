import { describe, expect, it } from 'vitest';

import { errorMessage } from './errors';

describe('errorMessage', () => {
  it('preserves a useful Error message', () => {
    expect(errorMessage(new Error('Render failed.'))).toBe('Render failed.');
  });

  it('returns a safe fallback for unknown thrown values', () => {
    expect(errorMessage(null)).toBe('An unexpected frontend error interrupted the page.');
  });
});
