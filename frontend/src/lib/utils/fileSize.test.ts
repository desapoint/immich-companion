import { describe, expect, it } from 'vitest';

import { formatByteDifference, formatBytes } from './fileSize';

describe('file size formatting', () => {
  it('uses a unit appropriate to the magnitude', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1536)).toBe('1.50 KB');
    expect(formatBytes(5 * 1024 ** 2)).toBe('5.00 MB');
    expect(formatBytes(12 * 1024 ** 3)).toBe('12.0 GB');
  });

  it('formats signed differences without forcing MB', () => {
    expect(formatByteDifference(0)).toBe('0 B');
    expect(formatByteDifference(512)).toBe('+512 B');
    expect(formatByteDifference(-1536)).toBe('−1.50 KB');
    expect(formatByteDifference(null)).toBe('—');
  });
});
