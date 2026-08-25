import type {
  AssetSelectionMode,
  AssetSelectionRequest,
  SearchGroup,
} from '../types/assets';
import { serializeSearchGroup } from './assetViewModel';

export interface AssetSelectionState {
  mode: AssetSelectionMode;
  selectedIds: Set<string>;
  excludedIds: Set<string>;
}

export function createAssetSelectionState(): AssetSelectionState {
  return { mode: 'explicit', selectedIds: new Set(), excludedIds: new Set() };
}

export function selectedAssetCount(
  state: AssetSelectionState,
  matchingTotal: number,
): number {
  return state.mode === 'all_matching'
    ? Math.max(0, matchingTotal - state.excludedIds.size)
    : state.selectedIds.size;
}

export function isAssetSelected(state: AssetSelectionState, assetId: string): boolean {
  return state.mode === 'all_matching'
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
  return { mode: 'all_matching', selectedIds: new Set(), excludedIds: new Set() };
}

export function buildSelectionRequest(
  state: AssetSelectionState,
  expression: SearchGroup,
): AssetSelectionRequest {
  if (state.mode === 'explicit') {
    return {
      mode: 'explicit',
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
