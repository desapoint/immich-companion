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
  toggleAssetSelection,
} from './assetSelection';

describe('asset selection', () => {
  it('supports exact page selection and inversion', () => {
    let state = selectCurrentPage(createAssetSelectionState(), ['one', 'two']);
    state = invertCurrentPage(state, ['two', 'three']);

    expect([...state.selectedIds]).toEqual(['one', 'three']);
    expect(selectedAssetCount(state, 20)).toBe(2);
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
