import { describe, expect, it } from 'vitest';

import {
  copySearchGroup,
  createSearchCondition,
  createSearchGroup,
  formatAssetBytes,
  nextViewerIndex,
  toggleSelectedAsset,
} from './assetViewModel';

describe('asset view model', () => {
  it('keeps viewer navigation inside result boundaries', () => {
    expect(nextViewerIndex(0, 'previous', 3)).toBe(0);
    expect(nextViewerIndex(0, 'next', 3)).toBe(1);
    expect(nextViewerIndex(2, 'next', 3)).toBe(2);
  });

  it('toggles selection without mutating the previous set', () => {
    const current = new Set(['first']);
    const added = toggleSelectedAsset(current, 'second');
    const removed = toggleSelectedAsset(added, 'first');

    expect(current).toEqual(new Set(['first']));
    expect(added).toEqual(new Set(['first', 'second']));
    expect(removed).toEqual(new Set(['second']));
  });

  it('formats compact file sizes', () => {
    expect(formatAssetBytes(null)).toBeNull();
    expect(formatAssetBytes(512)).toBe('512 B');
    expect(formatAssetBytes(1536)).toBe('1.5 KB');
    expect(formatAssetBytes(5 * 1024 ** 2)).toBe('5.0 MB');
  });

  it('copies nested search state without sharing child references', () => {
    const root = createSearchGroup();
    const nested = createSearchGroup('or');
    nested.children.push(createSearchCondition('album'));
    root.children.push(nested);

    const copied = copySearchGroup(root);
    expect(copied).toEqual(root);
    (copied.children[0] as typeof nested).negate = true;
    expect(nested.negate).toBe(false);
  });
});
