import { describe, expect, it } from 'vitest';
import {
  applyAssetRangeFromSnapshot,
  applyShiftAssetRange,
  emptyAssetSelection,
  getAssetSelectionCount,
  invertAssetSelection,
  isAssetSelected,
  selectAllMatchingAssets,
  selectVisibleAssets,
  toggleAssetSelected,
} from './assetSelection';

const ids = [10, 11, 12, 13, 14, 15];

describe('assetSelection', () => {
  it('selects visible assets without implying all matching assets', () => {
    const state = selectVisibleAssets([10, 11, 12]);
    expect([...state.selectedIds]).toEqual([10, 11, 12]);
    expect(state.allMatchingSelected).toBe(false);
    expect(state.anchor).toBe(10);
  });

  it('represents select-all with exclusions', () => {
    let state = selectAllMatchingAssets(10);
    state = toggleAssetSelected(state, 12);
    expect(state.allMatchingSelected).toBe(true);
    expect(isAssetSelected(state, 12)).toBe(false);
    expect(getAssetSelectionCount(state, 100)).toBe(99);
  });

  it('inverts explicit selection into all-matching exclusions', () => {
    let state = emptyAssetSelection();
    state = toggleAssetSelected(state, 10);
    state = toggleAssetSelected(state, 12);
    state = invertAssetSelection(state);
    expect(state.allMatchingSelected).toBe(true);
    expect(isAssetSelected(state, 10)).toBe(false);
    expect(isAssetSelected(state, 11)).toBe(true);
    expect(isAssetSelected(state, 12)).toBe(false);
  });

  it('shift-adds toward an unselected destination', () => {
    let state = toggleAssetSelected(emptyAssetSelection(), 10);
    state = applyShiftAssetRange(state, ids, 13);
    expect(ids.filter((id) => isAssetSelected(state, id))).toEqual([10, 11, 12, 13]);
    expect(state.anchor).toBe(10);
  });

  it('shift-removes toward a selected destination', () => {
    let state = selectVisibleAssets(ids);
    state.anchor = 10;
    state = applyShiftAssetRange(state, ids, 13);
    expect(ids.filter((id) => isAssetSelected(state, id))).toEqual([14, 15]);
    expect(state.anchor).toBe(10);
  });

  it('recomputes drag ranges from the gesture snapshot so moving backward shrinks the range', () => {
    const snapshot = toggleAssetSelected(emptyAssetSelection(), 15);
    const overshot = applyAssetRangeFromSnapshot(snapshot, ids, 10, 14, 'add');
    expect(ids.filter((id) => isAssetSelected(overshot, id))).toEqual(ids);

    const shrunk = applyAssetRangeFromSnapshot(snapshot, ids, 10, 12, 'add');
    expect(ids.filter((id) => isAssetSelected(shrunk, id))).toEqual([10, 11, 12, 15]);
  });

  it('recomputes drag deselection from the gesture snapshot', () => {
    const snapshot = selectVisibleAssets(ids);
    const state = applyAssetRangeFromSnapshot(snapshot, ids, 11, 14, 'remove');
    expect(ids.filter((id) => isAssetSelected(state, id))).toEqual([10, 15]);
  });
});
