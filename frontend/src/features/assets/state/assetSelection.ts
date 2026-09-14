import type {
  AssetSelectionMode,
  AssetSelectionRequest,
  SearchGroup,
  SelectionSetMembershipResponse,
} from '../types/assets';
import { serializeSearchGroup } from './assetViewModel';

export interface AssetSelectionState {
  mode: AssetSelectionMode;
  selectionId: string | null;
  selectionRevision: number | null;
  serverSelectedCount: number | null;
  selectedIds: Set<string>;
  excludedIds: Set<string>;
}

export interface AssetPageSelection {
  id: string;
  revision: number;
  selected_count: number;
  selected_ids: string[];
}

export function createAssetSelectionState(): AssetSelectionState {
  return {
    mode: 'explicit',
    selectionId: null,
    selectionRevision: null,
    serverSelectedCount: null,
    selectedIds: new Set(),
    excludedIds: new Set(),
  };
}

export function setExplicitAssetIds(assetIds: string[]): AssetSelectionState {
  return {
    mode: 'explicit',
    selectionId: null,
    selectionRevision: null,
    serverSelectedCount: null,
    selectedIds: new Set(assetIds),
    excludedIds: new Set(),
  };
}

export function buildExplicitAssetSelectionRequest(assetId: string): AssetSelectionRequest {
  return { mode: 'explicit', ids: [assetId], excluded_ids: [] };
}

export function selectedAssetCount(
  state: AssetSelectionState,
  matchingTotal: number,
): number {
  return state.selectionId !== null
    ? state.serverSelectedCount ?? state.selectedIds.size
    : state.mode === 'all_matching'
    ? Math.max(0, matchingTotal - state.excludedIds.size)
    : state.selectedIds.size;
}

export function isAssetSelected(state: AssetSelectionState, assetId: string): boolean {
  return state.selectionId !== null
    ? state.selectedIds.has(assetId)
    : state.mode === 'all_matching'
    ? !state.excludedIds.has(assetId)
    : state.selectedIds.has(assetId);
}

export function toggleAssetSelection(
  state: AssetSelectionState,
  assetId: string,
): AssetSelectionState {
  if (state.mode === 'all_matching') {
    const excludedIds = new Set(state.excludedIds);
    if (excludedIds.has(assetId)) excludedIds.delete(assetId);
    else excludedIds.add(assetId);
    return { ...state, excludedIds };
  }
  const selectedIds = new Set(state.selectedIds);
  if (selectedIds.has(assetId)) selectedIds.delete(assetId);
  else selectedIds.add(assetId);
  return { ...state, selectedIds };
}

export function setAssetsSelected(
  state: AssetSelectionState,
  assetIds: string[],
  selected: boolean,
): AssetSelectionState {
  if (state.mode === 'all_matching') {
    const excludedIds = new Set(state.excludedIds);
    assetIds.forEach((assetId) => {
      if (selected) excludedIds.delete(assetId);
      else excludedIds.add(assetId);
    });
    return { ...state, excludedIds };
  }
  const selectedIds = new Set(state.selectedIds);
  assetIds.forEach((assetId) => {
    if (selected) selectedIds.add(assetId);
    else selectedIds.delete(assetId);
  });
  return { ...state, selectedIds };
}

export function setSelectionRange(
  state: AssetSelectionState,
  pageIds: string[],
  anchorIndex: number,
  currentIndex: number,
  selected: boolean,
): AssetSelectionState {
  const start = Math.max(0, Math.min(anchorIndex, currentIndex));
  const end = Math.min(pageIds.length - 1, Math.max(anchorIndex, currentIndex));
  return setAssetsSelected(state, pageIds.slice(start, end + 1), selected);
}

export function selectCurrentPage(
  state: AssetSelectionState,
  pageIds: string[],
): AssetSelectionState {
  if (state.mode === 'all_matching') {
    const excludedIds = new Set(state.excludedIds);
    pageIds.forEach((identifier) => excludedIds.delete(identifier));
    return { ...state, excludedIds };
  }
  return { ...state, selectedIds: new Set([...state.selectedIds, ...pageIds]) };
}

export function invertCurrentPage(
  state: AssetSelectionState,
  pageIds: string[],
): AssetSelectionState {
  return pageIds.reduce(toggleAssetSelection, state);
}

export function selectAllMatching(): AssetSelectionState {
  return {
    ...createAssetSelectionState(),
    mode: 'all_matching',
  };
}

export function setServerSelection(
  state: AssetSelectionState,
  id: string,
  revision: number,
  selectedCount: number,
  visibleSelectedIds: string[] = [],
): AssetSelectionState {
  return {
    ...state,
    mode: 'explicit',
    selectionId: id,
    selectionRevision: revision,
    serverSelectedCount: selectedCount,
    selectedIds: new Set(visibleSelectedIds),
    excludedIds: new Set(),
  };
}

function canApplyServerSelectionPage(
  state: AssetSelectionState,
  page: AssetPageSelection,
): boolean {
  if (state.selectionId !== null && state.selectionId !== page.id) return false;
  return state.selectionRevision === null || page.revision >= state.selectionRevision;
}

export function canMergeServerSelectionPages(
  state: AssetSelectionState,
  pages: Array<AssetPageSelection | null | undefined>,
): boolean {
  const available = pages.filter((page): page is AssetPageSelection => page !== null && page !== undefined);
  if (available.length === 0) return true;
  const first = available[0];
  if (!canApplyServerSelectionPage(state, first)) return false;
  return available.every((page) => (
    page.id === first.id
    && page.revision === first.revision
    && canApplyServerSelectionPage(state, page)
  ));
}

export function mergeServerSelectionPages(
  state: AssetSelectionState,
  pages: Array<AssetPageSelection | null | undefined>,
): AssetSelectionState {
  const available = pages.filter((page): page is AssetPageSelection => page !== null && page !== undefined);
  if (available.length === 0 || !canMergeServerSelectionPages(state, available)) return state;
  const snapshot = available[0];
  return setServerSelection(
    state,
    snapshot.id,
    snapshot.revision,
    snapshot.selected_count,
    [...new Set(available.flatMap((page) => page.selected_ids))],
  );
}

export function mergeServerSelectionPage(
  state: AssetSelectionState,
  page: AssetPageSelection,
): AssetSelectionState {
  if (!canApplyServerSelectionPage(state, page)) return state;
  return setServerSelection(
    state,
    page.id,
    page.revision,
    page.selected_count,
    [...new Set([...state.selectedIds, ...page.selected_ids])],
  );
}

export function patchServerSelectionMembership(
  state: AssetSelectionState,
  requestedAssetIds: string[],
  membership: SelectionSetMembershipResponse,
): AssetSelectionState {
  if (state.selectionId !== membership.selection.id) return state;
  if (
    state.selectionRevision !== null
    && membership.selection.revision < state.selectionRevision
  ) return state;
  const selectedIds = new Set(state.selectedIds);
  requestedAssetIds.forEach((assetId) => selectedIds.delete(assetId));
  membership.selected_ids.forEach((assetId) => selectedIds.add(assetId));
  return {
    ...state,
    selectionRevision: membership.selection.revision,
    serverSelectedCount: membership.selection.selected_count,
    selectedIds,
  };
}

export function buildSelectionRequest(
  state: AssetSelectionState,
  expression: SearchGroup,
): AssetSelectionRequest {
  if (state.mode === 'explicit') {
    return {
      mode: 'explicit',
      selection_id: state.selectionId,
      ids: [...state.selectedIds],
      excluded_ids: [],
    };
  }
  return {
    mode: 'all_matching',
    ids: [],
    expression: serializeSearchGroup(expression),
    excluded_ids: [...state.excludedIds],
  };
}
