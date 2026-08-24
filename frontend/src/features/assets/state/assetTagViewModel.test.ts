import { describe, expect, it } from 'vitest';

import { safeAssetTagColor } from './assetTagViewModel';

describe('asset tag view model', () => {
  it('keeps six-digit tag colors and rejects unsafe CSS values', () => {
    expect(safeAssetTagColor('#2a9d8f')).toBe('#2a9d8f');
    expect(safeAssetTagColor('#ABCDEF')).toBe('#ABCDEF');
    expect(safeAssetTagColor('red; display: none')).toBe('var(--color-accent-strong)');
    expect(safeAssetTagColor(null)).toBe('var(--color-accent-strong)');
  });
});
