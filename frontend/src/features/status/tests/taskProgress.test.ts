import { describe, expect, it } from 'vitest';

import { formatTaskProgressPercent } from '../utils/taskProgress';

describe('task progress percentage', () => {
  it('shows at most two decimal places for fractional task progress', () => {
    expect(formatTaskProgressPercent((11000 / 25356) * 100)).toMatch(/^\d+\.\d{1,2}%$/);
    expect(formatTaskProgressPercent(12.345678)).toBe('12.35%');
    expect(formatTaskProgressPercent(12.3)).toBe('12.3%');
    expect(formatTaskProgressPercent(12)).toBe('12%');
  });

  it('does not show 100% until the task reaches completion', () => {
    expect(formatTaskProgressPercent(99.999)).toBe('99.99%');
    expect(formatTaskProgressPercent(100)).toBe('100%');
  });
});
