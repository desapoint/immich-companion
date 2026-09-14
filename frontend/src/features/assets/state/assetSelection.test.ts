import { describe, expect, it } from 'vitest';

import { createSearchGroup } from './assetViewModel';
import {
  buildSelectionRequest,
  buildExplicitAssetSelectionRequest,
  canMergeServerSelectionPages,
  createAssetSelectionState,
  invertCurrentPage,
  isAssetSelected,
  mergeServerSelectionPage,
  mergeServerSelectionPages,
  patchServerSelectionMembership,
  selectAllMatching,
  selectCurrentPage,
  selectedAssetCount,
  setSelectionRange,
  setServerSelection,
  toggleAssetSelection,
} from './assetSelection';

describe('asset selection', () => {
  it('supports exact page selection and inversion', () => {
    let state = selectCurrentPage(createAssetSelectionState(), ['one', 'two']);
    state = invertCurrentPage(state, ['two', 'three']);

    expect([...state.selectedIds]).toEqual(['one', 'three']);
    expect(selectedAssetCount(state, 20)).toBe(2);
  });

  it('builds an isolated one-asset request for viewer actions', () => {
    expect(buildExplicitAssetSelectionRequest('viewed')).toEqual({
      mode: 'explicit',
      ids: ['viewed'],
      excluded_ids: [],
    });
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

  it('keeps server selection totals while tracking only visible membership locally', () => {
    const state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      4,
      50000,
      ['visible-1', 'visible-2'],
    );

    expect(selectedAssetCount(state, 2)).toBe(50000);
    expect(isAssetSelected(state, 'visible-1')).toBe(true);
    expect(isAssetSelected(state, 'off-page')).toBe(false);
    expect(buildSelectionRequest(state, createSearchGroup())).toEqual({
      mode: 'explicit',
      selection_id: 'selection-1',
      ids: ['visible-1', 'visible-2'],
      excluded_ids: [],
    });
  });

  it('merges visible membership from one coherent server revision', () => {
    const state = mergeServerSelectionPages(createAssetSelectionState(), [
      { id: 'selection-1', revision: 4, selected_count: 8, selected_ids: ['one', 'two'] },
      { id: 'selection-1', revision: 4, selected_count: 8, selected_ids: ['three'] },
    ]);
    const appended = mergeServerSelectionPage(state, {
      id: 'selection-1',
      revision: 5,
      selected_count: 9,
      selected_ids: ['four'],
    });

    expect([...appended.selectedIds]).toEqual(['one', 'two', 'three', 'four']);
    expect(appended.selectionRevision).toBe(5);
    expect(appended.serverSelectedCount).toBe(9);
  });

  it('rejects mixed ids and revisions instead of combining incompatible membership', () => {
    const state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      5,
      9,
      ['current'],
    );
    const mixedRevision = [
      { id: 'selection-1', revision: 4, selected_count: 8, selected_ids: ['stale'] },
      { id: 'selection-1', revision: 5, selected_count: 9, selected_ids: ['fresh'] },
    ];
    const mixedIds = [
      { id: 'selection-1', revision: 5, selected_count: 9, selected_ids: ['fresh'] },
      { id: 'selection-2', revision: 5, selected_count: 3, selected_ids: ['other'] },
    ];

    expect(canMergeServerSelectionPages(state, mixedRevision)).toBe(false);
    expect(mergeServerSelectionPages(state, mixedRevision)).toBe(state);
    expect(canMergeServerSelectionPages(state, mixedIds)).toBe(false);
    expect(mergeServerSelectionPages(state, mixedIds)).toBe(state);
  });

  it('ignores stale page and membership revisions', () => {
    const state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      6,
      10,
      ['one', 'two'],
    );

    expect(mergeServerSelectionPage(state, {
      id: 'selection-1',
      revision: 5,
      selected_count: 9,
      selected_ids: ['stale'],
    })).toBe(state);

    expect(patchServerSelectionMembership(state, ['one'], {
      selection: {
        id: 'selection-1',
        revision: 5,
        selected_count: 9,
        status: 'active',
        expires_at: '2026-09-14T20:00:00Z',
      },
      selected_ids: [],
    })).toBe(state);
  });

  it('patches only requested visible membership during reconciliation', () => {
    const state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      4,
      10,
      ['one', 'two', 'three'],
    );
    const patched = patchServerSelectionMembership(state, ['two', 'four'], {
      selection: {
        id: 'selection-1',
        revision: 5,
        selected_count: 9,
        status: 'active',
        expires_at: '2026-09-14T20:00:00Z',
      },
      selected_ids: ['four'],
    });

    expect([...patched.selectedIds]).toEqual(['one', 'three', 'four']);
    expect(patched.selectionRevision).toBe(5);
    expect(patched.serverSelectedCount).toBe(9);
  });
});
