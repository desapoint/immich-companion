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
  selectCurrentPage,
  selectedAssetCount,
  setSelectionRange,
  setServerSelection,
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

  it('selects and deselects ordered page ranges', () => {
    const page = ['one', 'two', 'three', 'four'];
    let state = setSelectionRange(createAssetSelectionState(), page, 1, 3, true);
    state = setSelectionRange(state, page, 2, 3, false);
    expect([...state.selectedIds]).toEqual(['two']);
  });

  it('keeps all-matching as scope while using a revisioned explicit server selection', () => {
    let state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      4,
      50000,
      ['visible-1', 'visible-2'],
      'all_matching',
    );
    state = setSelectionRange(state, ['visible-1', 'visible-2'], 1, 1, false);

    expect(state.scope).toBe('all_matching');
    expect(selectedAssetCount(state, 50000)).toBe(50000);
    expect(isAssetSelected(state, 'visible-1')).toBe(true);
    expect(isAssetSelected(state, 'visible-2')).toBe(false);
    expect(buildSelectionRequest(state, createSearchGroup())).toEqual({
      mode: 'explicit',
      selection_id: 'selection-1',
      ids: ['visible-1'],
      excluded_ids: [],
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

  it('preserves selection scope while merging refreshed server membership', () => {
    const state = setServerSelection(
      createAssetSelectionState(),
      'selection-1',
      4,
      8,
      ['one'],
      'all_matching',
    );
    const merged = mergeServerSelectionPage(state, {
      id: 'selection-1',
      revision: 5,
      selected_count: 7,
      selected_ids: ['two'],
    });

    expect(merged.scope).toBe('all_matching');
    expect([...merged.selectedIds]).toEqual(['one', 'two']);
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
