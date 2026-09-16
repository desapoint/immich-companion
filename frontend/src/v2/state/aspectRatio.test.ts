import { describe, expect, it } from 'vitest';
import { formatAspectDecimal, invertAspectRatio, parseAspectRatio } from './aspectRatio';

describe('aspect ratio parsing', () => {
  it('accepts common ratio separators and normalizes to colon form', () => {
    for (const input of ['16:9', '16/9', '16-9', '16x9', '16×9']) {
      expect(parseAspectRatio(input)?.ratio).toBe('16:9');
    }
  });

  it('converts decimal input to a readable ratio', () => {
    const parsed = parseAspectRatio('1.778');
    expect(parsed?.source).toBe('decimal');
    expect(parsed?.ratio).toBe('16:9');
    expect(formatAspectDecimal(parsed?.decimal ?? 0)).toBe('1.778');
  });

  it('reduces ratio input and reports its decimal', () => {
    const parsed = parseAspectRatio('32:18');
    expect(parsed?.ratio).toBe('16:9');
    expect(formatAspectDecimal(parsed?.decimal ?? 0)).toBe('1.7778');
  });

  it('inverts ratios using normalized colon syntax', () => {
    expect(invertAspectRatio('16/9')).toBe('9:16');
    expect(invertAspectRatio('1.778')).toBe('9:16');
  });

  it('rejects zero, negative, and malformed ratios', () => {
    expect(parseAspectRatio('0')).toBeNull();
    expect(parseAspectRatio('16:0')).toBeNull();
    expect(parseAspectRatio('-1')).toBeNull();
    expect(parseAspectRatio('hello')).toBeNull();
  });
});
