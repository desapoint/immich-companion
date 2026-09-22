export const SIMILARITY_DEBUG_STORAGE_KEY = 'immichCompanionV2SimilarityDebugAssets';
export const SIMILARITY_DEBUG_CHANGED_EVENT = 'immich-companion-similarity-debug-changed';
const MAX_DEBUG_ASSETS = 12;

function storage(): Storage | null {
  return typeof window === 'undefined' ? null : window.localStorage;
}

function normalize(assetIds: readonly string[]): string[] {
  return [...new Set(assetIds.filter(Boolean))].slice(0, MAX_DEBUG_ASSETS);
}

export function readSimilarityDebugAssets(): string[] {
  const target = storage();
  if (!target) return [];
  try {
    const value = JSON.parse(target.getItem(SIMILARITY_DEBUG_STORAGE_KEY) ?? '[]');
    return Array.isArray(value) ? normalize(value.filter((item): item is string => typeof item === 'string')) : [];
  } catch {
    return [];
  }
}

function write(assetIds: readonly string[]): string[] {
  const value = normalize(assetIds);
  const target = storage();
  target?.setItem(SIMILARITY_DEBUG_STORAGE_KEY, JSON.stringify(value));
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent(SIMILARITY_DEBUG_CHANGED_EVENT, { detail: value }));
  return value;
}

export function addSimilarityDebugAssets(assetIds: readonly string[]): number {
  const before = readSimilarityDebugAssets();
  const after = write([...before, ...assetIds]);
  return after.length - before.length;
}

export function removeSimilarityDebugAsset(assetId: string): void {
  write(readSimilarityDebugAssets().filter((item) => item !== assetId));
}

export function clearSimilarityDebugAssets(): void {
  write([]);
}
