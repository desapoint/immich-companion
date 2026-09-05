export type AssetSelectionId = string | number;
export type AssetSelectionMode = 'add' | 'remove';

export type AssetSelectionState<T extends AssetSelectionId = AssetSelectionId> = {
  selectedIds: Set<T>;
  excludedIds: Set<T>;
  allMatchingSelected: boolean;
  anchor: T | null;
};

export function emptyAssetSelection<T extends AssetSelectionId>(): AssetSelectionState<T> {
  return { selectedIds: new Set<T>(), excludedIds: new Set<T>(), allMatchingSelected: false, anchor: null };
}

export function cloneAssetSelection<T extends AssetSelectionId>(state: AssetSelectionState<T>): AssetSelectionState<T> {
  return { selectedIds: new Set(state.selectedIds), excludedIds: new Set(state.excludedIds), allMatchingSelected: state.allMatchingSelected, anchor: state.anchor };
}

export function isAssetSelected<T extends AssetSelectionId>(state: AssetSelectionState<T>, id: T): boolean {
  return state.allMatchingSelected ? !state.excludedIds.has(id) : state.selectedIds.has(id);
}

export function getAssetSelectionCount<T extends AssetSelectionId>(state: AssetSelectionState<T>, total: number): number {
  return state.allMatchingSelected ? Math.max(0, total - state.excludedIds.size) : state.selectedIds.size;
}

export function isAllVisibleSelected<T extends AssetSelectionId>(state: AssetSelectionState<T>, ids: readonly T[]): boolean {
  return ids.length > 0 && ids.every((id) => isAssetSelected(state, id));
}

export function selectVisibleAssets<T extends AssetSelectionId>(ids: readonly T[]): AssetSelectionState<T> {
  return { selectedIds: new Set(ids), excludedIds: new Set<T>(), allMatchingSelected: false, anchor: ids[0] ?? null };
}

export function selectAllMatchingAssets<T extends AssetSelectionId>(anchor: T | null = null): AssetSelectionState<T> {
  return { selectedIds: new Set<T>(), excludedIds: new Set<T>(), allMatchingSelected: true, anchor };
}

export function invertAssetSelection<T extends AssetSelectionId>(state: AssetSelectionState<T>): AssetSelectionState<T> {
  if (state.allMatchingSelected) return { selectedIds: new Set(state.excludedIds), excludedIds: new Set<T>(), allMatchingSelected: false, anchor: state.anchor };
  return { selectedIds: new Set<T>(), excludedIds: new Set(state.selectedIds), allMatchingSelected: true, anchor: state.anchor };
}

export function setAssetSelected<T extends AssetSelectionId>(state: AssetSelectionState<T>, id: T, selected: boolean): AssetSelectionState<T> {
  const next = cloneAssetSelection(state);
  if (next.allMatchingSelected) {
    if (selected) next.excludedIds.delete(id); else next.excludedIds.add(id);
  } else {
    if (selected) next.selectedIds.add(id); else next.selectedIds.delete(id);
  }
  return next;
}

export function toggleAssetSelected<T extends AssetSelectionId>(state: AssetSelectionState<T>, id: T): AssetSelectionState<T> {
  const next = setAssetSelected(state, id, !isAssetSelected(state, id));
  next.anchor = id;
  return next;
}

export function assetRange<T extends AssetSelectionId>(ids: readonly T[], fromId: T, toId: T): T[] {
  const from = ids.indexOf(fromId), to = ids.indexOf(toId);
  if (from < 0 || to < 0) return [toId];
  return ids.slice(Math.min(from, to), Math.max(from, to) + 1);
}

export function applyAssetRange<T extends AssetSelectionId>(state: AssetSelectionState<T>, ids: readonly T[], fromId: T, toId: T, mode: AssetSelectionMode): AssetSelectionState<T> {
  let next = cloneAssetSelection(state);
  for (const id of assetRange(ids, fromId, toId)) next = setAssetSelected(next, id, mode === 'add');
  return next;
}

export function applyAssetRangeFromSnapshot<T extends AssetSelectionId>(snapshot: AssetSelectionState<T>, ids: readonly T[], fromId: T, toId: T, mode: AssetSelectionMode): AssetSelectionState<T> {
  return applyAssetRange(cloneAssetSelection(snapshot), ids, fromId, toId, mode);
}

export function applyShiftAssetRange<T extends AssetSelectionId>(state: AssetSelectionState<T>, ids: readonly T[], toId: T): AssetSelectionState<T> {
  if (state.anchor === null) return toggleAssetSelected(state, toId);
  const mode: AssetSelectionMode = isAssetSelected(state, toId) ? 'remove' : 'add';
  const next = applyAssetRange(state, ids, state.anchor, toId, mode);
  next.anchor = state.anchor;
  return next;
}
