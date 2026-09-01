import { describe, expect, it } from 'vitest';

import { resolveStackPrimary } from './duplicateReview';

describe('resolveStackPrimary', () => {
  it('keeps a valid explicit primary', () => {
    expect(resolveStackPrimary(['one', 'two'], 'two', ['one'])).toBe('two');
  });

  it('uses the preferred stack member when no primary was selected', () => {
    expect(resolveStackPrimary(['one', 'two'], null, ['two'])).toBe('two');
  });

  it('always falls back to the first stack member', () => {
    expect(resolveStackPrimary(['one', 'two'], null, ['missing'])).toBe('one');
  });

  it('returns null when no member is marked Stack', () => {
    expect(resolveStackPrimary([], null, ['one'])).toBeNull();
  });
});
