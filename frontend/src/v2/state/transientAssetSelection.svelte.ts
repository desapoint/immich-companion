import {
  emptyAssetSelection,
  type AssetSelectionState,
} from '../components/assetSelection';

const RESTORE_SELECTION_STORAGE_KEY = 'immich-companion:v2:restore-selection';

type SelectionStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

type StoredSelection = {
  selectedIds: string[];
  excludedIds: string[];
  allMatchingSelected: boolean;
  anchor: string | null;
};

function parseStoredSelection(value: string | null): AssetSelectionState<string> {
  if (!value) return emptyAssetSelection<string>();
  try {
    const parsed = JSON.parse(value) as Partial<StoredSelection>;
    if (!Array.isArray(parsed.selectedIds) || !Array.isArray(parsed.excludedIds)) return emptyAssetSelection<string>();
    if (!parsed.selectedIds.every((id) => typeof id === 'string') || !parsed.excludedIds.every((id) => typeof id === 'string')) return emptyAssetSelection<string>();
    if (typeof parsed.allMatchingSelected !== 'boolean') return emptyAssetSelection<string>();
    if (parsed.anchor !== null && typeof parsed.anchor !== 'string') return emptyAssetSelection<string>();
    return {
      selectedIds: new Set(parsed.selectedIds),
      excludedIds: new Set(parsed.excludedIds),
      allMatchingSelected: parsed.allMatchingSelected,
      anchor: parsed.anchor ?? null,
    };
  } catch {
    return emptyAssetSelection<string>();
  }
}

export class TransientAssetSelectionController {
  selection = $state<AssetSelectionState<string>>(emptyAssetSelection<string>());

  constructor(
    private readonly storageKey = RESTORE_SELECTION_STORAGE_KEY,
    private readonly storage: SelectionStorage | null = typeof sessionStorage === 'undefined' ? null : sessionStorage,
  ) {
    this.selection = parseStoredSelection(this.storage?.getItem(this.storageKey) ?? null);
  }

  snapshot(): AssetSelectionState<string> {
    return this.selection;
  }

  replace(next: AssetSelectionState<string>): void {
    this.selection = next;
    if (!next.allMatchingSelected && next.selectedIds.size === 0) {
      this.storage?.removeItem(this.storageKey);
      return;
    }
    this.storage?.setItem(this.storageKey, JSON.stringify({
      selectedIds: [...next.selectedIds],
      excludedIds: [...next.excludedIds],
      allMatchingSelected: next.allMatchingSelected,
      anchor: next.anchor,
    } satisfies StoredSelection));
  }

  clear(): void {
    this.replace(emptyAssetSelection<string>());
  }
}
