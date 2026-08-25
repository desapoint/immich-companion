import { describe, expect, it } from 'vitest';

import { createSearchGroup } from './assetViewModel';
import {
  buildSelectionRequest,
  createAssetSelectionState,
  invertCurrentPage,
  isAssetSelected,
  selectAllMatching,
  selectCurrentPage,
  selectedAssetCount,
  setSelectionRange,
  toggleAssetSelection,
} from './assetSelection';

describe('asset selection', () => {
  it('supports exact page selection and inversion', () => {
    let state = selectCurrentPage(createAssetSelectionState(), ['one', 'two']);
    state = invertCurrentPage(state, ['two', 'three']);

    expect([...state.selectedIds]).toEqual(['one', 'three']);
    expect(selectedAssetCount(state, 20)).toBe(2);
  });

  it('selects and deselects ordered page ranges in either selection mode', () => {
    const page = ['one', 'two', 'three', 'four'];
    let explicit = setSelectionRange(createAssetSelectionState(), page, 1, 3, true);
    explicit = setSelectionRange(explicit, page, 2, 3, false);
    expect([...explicit.selectedIds]).toEqual(['two']);

    let matching = selectAllMatching();
    matching = setSelectionRange(matching, page, 1, 2, false);
    matching = setSelectionRange(matching, page, 2, 2, true);
    expect([...matching.excludedIds]).toEqual(['two']);
  });

  it('models all matching with explicit exclusions', () => {
    let state = selectAllMatching();
    state = toggleAssetSelection(state, 'excluded');

    expect(isAssetSelected(state, 'included')).toBe(true);
    expect(isAssetSelected(state, 'excluded')).toBe(false);
    expect(selectedAssetCount(state, 66)).toBe(65);
    expect(buildSelectionRequest(state, createSearchGroup())).toMatchObject({
      mode: 'all_matching',
      ids: [],
      excluded_ids: ['excluded'],
      expression: { kind: 'group', operator: 'and', children: [] },
    });
  });
});
