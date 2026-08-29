export type AssetListMode = 'paged' | 'infinite';

export interface InfiniteScrollAnchor {
  id: string;
  top: number;
}

export const ASSET_LIST_MODE_STORAGE_KEY = 'immich-companion:asset-list-mode';

export function decodeAssetListMode(value: string | null): AssetListMode {
  return value === 'infinite' ? 'infinite' : 'paged';
}

export function infiniteWindowPages(loadedThroughPage: number, availablePages: number): number[] {
  const count = Math.min(
    Math.max(1, Math.trunc(loadedThroughPage)),
    Math.max(1, Math.trunc(availablePages)),
  );
  return Array.from({ length: count }, (_, index) => index + 1);
}

export function mergeInfiniteWindowItems<T extends { id: string }>(pages: T[][]): T[] {
  const seen = new Set<string>();
  const items: T[] = [];
  for (const page of pages) {
    for (const item of page) {
      if (seen.has(item.id)) continue;
      seen.add(item.id);
      items.push(item);
    }
  }
  return items;
}

export function firstSurvivingScrollAnchor(
  anchors: InfiniteScrollAnchor[],
  loadedIds: ReadonlySet<string>,
): InfiniteScrollAnchor | null {
  return anchors.find((anchor) => loadedIds.has(anchor.id)) ?? null;
}
