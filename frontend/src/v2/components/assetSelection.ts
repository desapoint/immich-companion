export type AssetSelectionMode = 'add' | 'remove';

export type AssetSelectionState = {
  selectedIds: Set<number>;
  excludedIds: Set<number>;
  allMatchingSelected: boolean;
  anchor: number | null;
};

export function emptyAssetSelection(): AssetSelectionState {
  return {
    selectedIds: new Set(),
    excludedIds: new Set(),
    allMatchingSelected: false,
    anchor: null,
  };
}

export function cloneAssetSelection(state: AssetSelectionState): AssetSelectionState {
  return {
    selectedIds: new Set(state.selectedIds),
    excludedIds: new Set(state.excludedIds),
    allMatchingSelected: state.allMatchingSelected,
    anchor: state.anchor,
  };
}

export function isAssetSelected(state: AssetSelectionState, id: number): boolean {
  return state.allMatchingSelected ? !state.excludedIds.has(id) : state.selectedIds.has(id);
}

export function getAssetSelectionCount(state: AssetSelectionState, total: number): number {
  return state.allMatchingSelected ? Math.max(0, total - state.excludedIds.size) : state.selectedIds.size;
}

export function selectVisibleAssets(ids: readonly number[]): AssetSelectionState {
  return {
    selectedIds: new Set(ids),
    excludedIds: new Set(),
    allMatchingSelected: false,
    anchor: ids[0] ?? null,
  };
}

export function selectAllMatchingAssets(anchor: number | null = null): AssetSelectionState {
  return {
    selectedIds: new Set(),
    excludedIds: new Set(),
    allMatchingSelected: true,
    anchor,
  };
}

export function invertAssetSelection(state: AssetSelectionState): AssetSelectionState {
  if (state.allMatchingSelected) {
    return {
      selectedIds: new Set(state.excludedIds),
      excludedIds: new Set(),
      allMatchingSelected: false,
      anchor: state.anchor,
    };
  }

  return {
    selectedIds: new Set(),
    excludedIds: new Set(state.selectedIds),
    allMatchingSelected: true,
    anchor: state.anchor,
  };
}

export function setAssetSelected(state: AssetSelectionState, id: number, selected: boolean): AssetSelectionState {
  const next = cloneAssetSelection(state);
  if (next.allMatchingSelected) {
    if (selected) next.excludedIds.delete(id);
    else next.excludedIds.add(id);
  } else {
    if (selected) next.selectedIds.add(id);
    else next.selectedIds.delete(id);
  }
  return next;
}

export function toggleAssetSelected(state: AssetSelectionState, id: number): AssetSelectionState {
  const next = setAssetSelected(state, id, !isAssetSelected(state, id));
  next.anchor = id;
  return next;
}

export function assetRange(ids: readonly number[], fromId: number, toId: number): number[] {
  const from = ids.indexOf(fromId);
  const to = ids.indexOf(toId);
  if (from < 0 || to < 0) return [toId];
  const min = Math.min(from, to);
  const max = Math.max(from, to);
  return ids.slice(min, max + 1);
}

export function applyAssetRange(
  state: AssetSelectionState,
  ids: readonly number[],
  fromId: number,
  toId: number,
  mode: AssetSelectionMode,
): AssetSelectionState {
  let next = cloneAssetSelection(state);
  for (const id of assetRange(ids, fromId, toId)) {
    next = setAssetSelected(next, id, mode === 'add');
  }
  return next;
}

export function applyAssetRangeFromSnapshot(
  snapshot: AssetSelectionState,
  ids: readonly number[],
  fromId: number,
  toId: number,
  mode: AssetSelectionMode,
): AssetSelectionState {
  return applyAssetRange(cloneAssetSelection(snapshot), ids, fromId, toId, mode);
}

export function applyShiftAssetRange(
  state: AssetSelectionState,
  ids: readonly number[],
  toId: number,
): AssetSelectionState {
  if (state.anchor === null) return toggleAssetSelected(state, toId);
  const mode: AssetSelectionMode = isAssetSelected(state, toId) ? 'remove' : 'add';
  const next = applyAssetRange(state, ids, state.anchor, toId, mode);
  next.anchor = state.anchor;
  return next;
}
