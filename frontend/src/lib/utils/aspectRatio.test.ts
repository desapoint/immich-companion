import { describe, expect, it } from 'vitest';

import { aspectRatioValidationMessage, parseAspectRatioInput } from './aspectRatio';

describe('aspect ratio input', () => {
  it('accepts decimals and fractions without rounding away precision', () => {
    expect(parseAspectRatioInput('1.7777777778')).toBeCloseTo(1.7777777778, 10);
    expect(parseAspectRatioInput(' 16 / 9 ')).toBeCloseTo(16 / 9, 12);
    expect(parseAspectRatioInput('4/3')).toBeCloseTo(4 / 3, 12);
  });

  it('rejects zero, negatives, malformed fractions, and CSS-like input', () => {
    for (const value of ['0', '-1', '16/0', '16/9/2', 'wide', '1; color:red']) {
      expect(() => parseAspectRatioInput(value)).toThrow();
      expect(aspectRatioValidationMessage(value)).not.toBe('');
    }
  });
});
